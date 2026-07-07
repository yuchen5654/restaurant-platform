from decimal import Decimal
from datetime import datetime, timezone, timedelta
import logging
import uuid as _uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import DepletionEvent
from app.models.recipe import MenuItem
from app.models.sales import SalesByItem, SalesSummary

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
    source: str = 'manual',
    channel: str = 'dine_in',
) -> SalesByItem:
    """Decrement ingredient stock and record a SalesByItem row. Caller commits."""
    menu_item = db.get(MenuItem, _to_uuid(menu_item_id))
    if not menu_item or menu_item.restaurant_id != _to_uuid(restaurant_id):
        raise ValueError(f'Menu item {menu_item_id} not found')

    total_food_cost = Decimal('0')
    for recipe_line in menu_item.recipe_lines:
        # Only deplete lines applicable to this sale's channel.
        # channel=None on the recipe line means "all channels".
        if recipe_line.channel is not None and recipe_line.channel != channel:
            continue
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
        db.add(DepletionEvent(
            restaurant_id = recipe_line.ingredient.restaurant_id,
            ingredient_id = ingredient.id,
            menu_item_id  = _to_uuid(menu_item_id),
            quantity      = qty_consumed,
            depleted_at   = business_date,
        ))

    record = SalesByItem(
        restaurant_id = restaurant_id,
        menu_item_id  = menu_item_id,
        business_date = business_date,
        quantity_sold = quantity_sold,
        gross_revenue = Decimal(str(gross_revenue)),
        food_cost     = total_food_cost,
        source        = source,
        channel       = channel,
    )
    db.add(record)
    return record


def _upsert_sales_summary(
    db: Session,
    restaurant_id: str,
    business_date: datetime,
    gross_revenue: Decimal,
    covers: int,
) -> None:
    """Add covers and revenue to the SalesSummary row for this date, creating if absent."""
    rid = _to_uuid(restaurant_id)
    # Find any existing summary row for this calendar date
    bd = business_date if business_date.tzinfo else business_date.replace(tzinfo=timezone.utc)
    day_start = datetime(bd.year, bd.month, bd.day, tzinfo=timezone.utc)
    day_end   = day_start + timedelta(days=1)

    existing = db.execute(
        select(SalesSummary)
        .where(
            SalesSummary.restaurant_id == rid,
            SalesSummary.business_date >= day_start,
            SalesSummary.business_date <  day_end,
        )
        .limit(1)
    ).scalar_one_or_none()

    if existing:
        existing.gross_revenue = (existing.gross_revenue or Decimal('0')) + gross_revenue
        existing.covers        = (existing.covers or 0) + covers
    else:
        db.add(SalesSummary(
            restaurant_id = rid,
            business_date = business_date,
            gross_revenue = gross_revenue,
            covers        = covers,
            source        = 'manual',
        ))


def deplete_batch(
    db: Session,
    restaurant_id: str,
    sales: list[dict],
    business_date: datetime,
    covers: int = 0,
) -> list[SalesByItem]:
    """Process multiple item sales in one transaction (end-of-day entry)."""
    records = [
        deplete_from_sale(
            db, restaurant_id,
            s['menu_item_id'], s['quantity'], business_date, s['revenue'],
            source=s.get('source', 'manual'),
            channel=s.get('channel', 'dine_in'),
        )
        for s in sales
    ]

    total_revenue = sum(r.gross_revenue for r in records)
    _upsert_sales_summary(db, restaurant_id, business_date, total_revenue, covers)

    db.commit()
    return records
