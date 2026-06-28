from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.sales import SalesByItem


def get_food_cost_summary(
    db: Session,
    restaurant_id: str,
    date_from: datetime,
    date_to: datetime,
) -> dict:
    r = db.execute(select(
        func.sum(SalesByItem.gross_revenue).label('revenue'),
        func.sum(SalesByItem.food_cost).label('food_cost'),
    ).where(
        SalesByItem.restaurant_id == restaurant_id,
        SalesByItem.business_date >= date_from,
        SalesByItem.business_date <= date_to,
        SalesByItem.menu_item_id.is_not(None),
    )).one()
    rev = float(r.revenue or 0)
    fc  = float(r.food_cost or 0)
    return {
        'date_from':        date_from.isoformat(),
        'date_to':          date_to.isoformat(),
        'total_revenue':    rev,
        'total_food_cost':  fc,
        'food_cost_pct':    round(fc / rev * 100, 2) if rev > 0 else None,
    }


def get_item_profitability(
    db: Session,
    restaurant_id: str,
    date_from: datetime,
    date_to: datetime,
    limit: int = 20,
) -> list[dict]:
    rows = db.execute(select(
        SalesByItem.menu_item_id,
        func.sum(SalesByItem.quantity_sold).label('qty'),
        func.sum(SalesByItem.gross_revenue).label('rev'),
        func.sum(SalesByItem.food_cost).label('fc'),
        (func.sum(SalesByItem.gross_revenue) -
         func.sum(SalesByItem.food_cost)).label('profit'),
    ).where(
        SalesByItem.restaurant_id == restaurant_id,
        SalesByItem.business_date >= date_from,
        SalesByItem.business_date <= date_to,
        SalesByItem.menu_item_id.is_not(None),
    ).group_by(
        SalesByItem.menu_item_id,
    ).order_by(
        (func.sum(SalesByItem.gross_revenue) -
         func.sum(SalesByItem.food_cost)).desc(),
    ).limit(limit)).all()

    return [
        {
            'menu_item_id':  str(r.menu_item_id),
            'quantity_sold': r.qty,
            'revenue':       float(r.rev or 0),
            'food_cost':     float(r.fc or 0),
            'gross_profit':  float(r.profit or 0),
            'food_cost_pct': round(float(r.fc or 0) / float(r.rev) * 100, 2) if r.rev else None,
        }
        for r in rows
    ]
