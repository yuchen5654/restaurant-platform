from decimal import Decimal
from datetime import datetime
import logging
import uuid as _uuid

from sqlalchemy.orm import Session

from app.models.recipe import MenuItem
from app.models.sales import SalesByItem

logger = logging.getLogger(__name__)


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


def deplete_from_sale(
    db: Session,
    restaurant_id: str,
    menu_item_id: str,
    quantity_sold: int,
    business_date: datetime,
    gross_revenue: float,
) -> SalesByItem:
    """Decrement ingredient stock and record a SalesByItem row. Caller commits."""
    menu_item = db.get(MenuItem, _to_uuid(menu_item_id))
    if not menu_item or menu_item.restaurant_id != _to_uuid(restaurant_id):
        raise ValueError(f'Menu item {menu_item_id} not found')

    total_food_cost = Decimal('0')
    for recipe_line in menu_item.recipe_lines:
        ingredient = recipe_line.ingredient
        if not ingredient:
            logger.warning(f'RecipeLine {recipe_line.id} has no ingredient — skipping')
            continue
        qty_consumed = Decimal(str(recipe_line.quantity)) * quantity_sold
        prev_stock   = ingredient.current_stock or Decimal('0')
        if prev_stock < qty_consumed:
            logger.warning(
                f'Stock for {ingredient.name} would go negative '
                f'(have {prev_stock}, consuming {qty_consumed}). '
                f'Check inventory count accuracy for restaurant {restaurant_id}.'
            )
        ingredient.current_stock = max(Decimal('0'), prev_stock - qty_consumed)
        if ingredient.current_cost_per_unit:
            total_food_cost += qty_consumed * ingredient.current_cost_per_unit

    record = SalesByItem(
        restaurant_id = restaurant_id,
        menu_item_id  = menu_item_id,
        business_date = business_date,
        quantity_sold = quantity_sold,
        gross_revenue = Decimal(str(gross_revenue)),
        food_cost     = total_food_cost,
    )
    db.add(record)
    return record


def deplete_batch(
    db: Session,
    restaurant_id: str,
    sales: list[dict],
    business_date: datetime,
) -> list[SalesByItem]:
    """Process multiple item sales in one transaction (end-of-day POS import)."""
    records = [
        deplete_from_sale(
            db, restaurant_id,
            s['menu_item_id'], s['quantity'], business_date, s['revenue'],
        )
        for s in sales
    ]
    db.commit()
    return records
