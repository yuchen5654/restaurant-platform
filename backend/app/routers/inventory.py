"""Inventory-facing HTTP endpoints: ingredient list, batch count, waste log."""
import uuid as _uuid
from datetime import datetime, timezone
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
