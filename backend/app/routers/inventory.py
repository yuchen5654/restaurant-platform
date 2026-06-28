"""Inventory-facing HTTP endpoints: ingredient CRUD, batch count, waste log."""
import uuid as _uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.inventory import Ingredient, InventoryCount
from app.routers.auth import get_current_restaurant_id
from app.services.inventory_service import log_waste

ingredients_router = APIRouter(prefix='/ingredients',       tags=['inventory'])
counts_router      = APIRouter(prefix='/inventory-counts',  tags=['inventory'])
waste_router       = APIRouter(prefix='/waste',             tags=['inventory'])


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


# ---------------------------------------------------------------------------
# Ingredient schemas
# ---------------------------------------------------------------------------

class _IngredientCreate(BaseModel):
    name:                  str
    category:              Optional[str]     = None
    unit:                  str
    current_cost_per_unit: Decimal
    par_level:             Optional[Decimal] = None
    reorder_qty:           Optional[Decimal] = None
    current_stock:         Optional[Decimal] = Decimal('0')


class _IngredientPatch(BaseModel):
    name:                  Optional[str]     = None
    category:              Optional[str]     = None
    unit:                  Optional[str]     = None
    current_cost_per_unit: Optional[Decimal] = None
    par_level:             Optional[Decimal] = None
    reorder_qty:           Optional[Decimal] = None
    current_stock:         Optional[Decimal] = None


# ---------------------------------------------------------------------------
# Ingredients
# ---------------------------------------------------------------------------

@ingredients_router.get('/')
def list_ingredients(
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return (
        db.query(Ingredient)
        .filter(Ingredient.restaurant_id == _to_uuid(rid))
        .order_by(Ingredient.category.nullslast(), Ingredient.name)
        .all()
    )


@ingredients_router.post('/', status_code=201)
def create_ingredient(
    body: _IngredientCreate,
    db:   Session = Depends(get_db),
    rid:  str     = Depends(get_current_restaurant_id),
):
    ing = Ingredient(
        restaurant_id         = _to_uuid(rid),
        name                  = body.name,
        category              = body.category,
        unit                  = body.unit,
        current_cost_per_unit = body.current_cost_per_unit,
        par_level             = body.par_level,
        reorder_qty           = body.reorder_qty,
        current_stock         = body.current_stock if body.current_stock is not None else Decimal('0'),
    )
    db.add(ing)
    db.commit()
    db.refresh(ing)
    return ing


@ingredients_router.patch('/{ingredient_id}')
def update_ingredient(
    ingredient_id: str,
    body: _IngredientPatch,
    db:   Session = Depends(get_db),
    rid:  str     = Depends(get_current_restaurant_id),
):
    rid_uuid = _to_uuid(rid)
    ing      = db.get(Ingredient, _to_uuid(ingredient_id))
    if not ing or ing.restaurant_id != rid_uuid:
        raise HTTPException(404, 'Ingredient not found')
    # Only update fields the caller explicitly included in the request body.
    for field in body.model_fields_set:
        setattr(ing, field, getattr(body, field))
    db.commit()
    db.refresh(ing)
    return ing


# ---------------------------------------------------------------------------
# Batch inventory count
# ---------------------------------------------------------------------------

class _CountItem(BaseModel):
    ingredient_id: str
    quantity:      float

class _BatchCount(BaseModel):
    items: list[_CountItem]


@counts_router.post('/', status_code=201)
def submit_batch_count(
    body: _BatchCount,
    db:   Session = Depends(get_db),
    rid:  str     = Depends(get_current_restaurant_id),
):
    rid_uuid = _to_uuid(rid)
    now      = datetime.now(timezone.utc)
    names    = []
    for item in body.items:
        ing = db.get(Ingredient, _to_uuid(item.ingredient_id))
        if not ing or ing.restaurant_id != rid_uuid:
            raise HTTPException(404, f'Ingredient {item.ingredient_id} not found')
        db.add(InventoryCount(
            restaurant_id = rid_uuid,
            ingredient_id = ing.id,
            counted_at    = now,
            quantity      = item.quantity,
        ))
        ing.current_stock = item.quantity
        names.append(ing.name)
    db.commit()
    return {'committed': len(names), 'ingredients': names}


# ---------------------------------------------------------------------------
# Waste log
# ---------------------------------------------------------------------------

class _WasteEntry(BaseModel):
    ingredient_id: str
    quantity:      float
    reason:        str
    notes:         Optional[str] = None


@waste_router.post('/', status_code=201)
def log_waste_entry(
    body: _WasteEntry,
    db:   Session = Depends(get_db),
    rid:  str     = Depends(get_current_restaurant_id),
):
    try:
        entry = log_waste(db, rid, body.ingredient_id, body.quantity, body.reason, body.notes)
        return {'id': str(entry.id), 'ok': True}
    except ValueError as exc:
        raise HTTPException(404, str(exc))
