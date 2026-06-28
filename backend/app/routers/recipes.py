import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.recipe import MenuItem, RecipeLine
from app.routers.auth import get_current_restaurant_id
from app.schemas.recipe import MenuItemCreate, RecipeLineCreate

router = APIRouter(prefix='/menu-items', tags=['recipes'])


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


@router.get('/')
def list_menu_items(
    db: Session = Depends(get_db),
    rid: str = Depends(get_current_restaurant_id),
):
    return (
        db.query(MenuItem)
        .filter(MenuItem.restaurant_id == _to_uuid(rid), MenuItem.is_active.is_(True))
        .order_by(MenuItem.category, MenuItem.name)
        .all()
    )


@router.post('/', status_code=201)
def create_menu_item(
    item: MenuItemCreate,
    db: Session = Depends(get_db),
    rid: str = Depends(get_current_restaurant_id),
):
    obj = MenuItem(**item.model_dump(), restaurant_id=_to_uuid(rid))
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.post('/{item_id}/recipe-lines', status_code=201)
def add_recipe_line(
    item_id: str,
    line: RecipeLineCreate,
    db: Session = Depends(get_db),
    rid: str = Depends(get_current_restaurant_id),
):
    mi = db.get(MenuItem, _to_uuid(item_id))
    if not mi or mi.restaurant_id != _to_uuid(rid):
        raise HTTPException(404, 'Not found')
    rl = RecipeLine(
        menu_item_id=_to_uuid(item_id),
        ingredient_id=_to_uuid(line.ingredient_id),
        quantity=line.quantity,
        unit=line.unit,
        notes=line.notes,
    )
    db.add(rl)
    db.commit()
    db.refresh(rl)
    return rl


@router.get('/{item_id}/food-cost')
def get_item_food_cost(
    item_id: str,
    db: Session = Depends(get_db),
    rid: str = Depends(get_current_restaurant_id),
):
    mi = db.get(MenuItem, _to_uuid(item_id))
    if not mi or mi.restaurant_id != _to_uuid(rid):
        raise HTTPException(404, 'Not found')
    return {
        'name':             mi.name,
        'menu_price':       float(mi.menu_price),
        'theoretical_cost': mi.theoretical_food_cost,
        'food_cost_pct':    mi.food_cost_pct,
        'recipe': [
            {
                'ingredient': rl.ingredient.name,
                'qty':        float(rl.quantity),
                'unit':       rl.unit,
                'line_cost':  rl.line_cost,
            }
            for rl in mi.recipe_lines
        ],
    }
