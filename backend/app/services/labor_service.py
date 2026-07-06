from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.labor import LaborEntry
from app.models.sales import SalesByItem, SalesSummary
import uuid as _uuid

_DOW_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


def get_prime_cost(db: Session, restaurant_id: str, window_days: int = 28) -> dict:
    rid   = _to_uuid(restaurant_id)
    since = datetime.now(timezone.utc) - timedelta(days=window_days)

    labor = db.execute(
        select(
            func.coalesce(func.sum(LaborEntry.labor_cost), 0).label('total_labor'),
            func.coalesce(func.sum(LaborEntry.hours), 0).label('total_hours'),
        )
        .where(LaborEntry.restaurant_id == rid, LaborEntry.business_date >= since)
    ).one()

    sales = db.execute(
        select(
            func.coalesce(func.sum(SalesByItem.gross_revenue), 0).label('rev'),
            func.coalesce(func.sum(SalesByItem.food_cost), 0).label('food'),
        )
        .where(SalesByItem.restaurant_id == rid, SalesByItem.business_date >= since)
    ).one()

    total_rev   = float(sales.rev)
    total_food  = float(sales.food)
    total_labor = float(labor.total_labor)

    if total_rev == 0:
        return {
            'food_cost_pct': None, 'labor_pct': None, 'prime_cost_pct': None,
            'flag_over_62': False, 'sales_per_labor_hour_by_dow': [],
            'data_gap': 'no sales data in window',
        }

    food_pct   = round(total_food  / total_rev * 100, 2)
    labor_pct  = round(total_labor / total_rev * 100, 2)
    prime_pct  = round(food_pct + labor_pct, 2)

    # Sales per labor hour by day-of-week
    summaries = db.execute(
        select(SalesSummary).where(SalesSummary.restaurant_id == rid, SalesSummary.business_date >= since)
    ).scalars().all()

    labor_entries = db.execute(
        select(LaborEntry).where(LaborEntry.restaurant_id == rid, LaborEntry.business_date >= since)
    ).scalars().all()

    dow_rev   = [0.0] * 7
    dow_hours = [0.0] * 7
    for s in summaries:
        dow_rev[s.business_date.weekday()] += float(s.gross_revenue or 0)
    for le in labor_entries:
        dow_hours[le.business_date.weekday()] += float(le.hours or 0)

    dow_out = [
        {
            'weekday':              i,
            'weekday_name':         _DOW_NAMES[i],
            'sales_per_labor_hour': round(dow_rev[i] / dow_hours[i], 2) if dow_hours[i] > 0 else None,
        }
        for i in range(7)
    ]

    return {
        'food_cost_pct':             food_pct,
        'labor_pct':                 labor_pct,
        'prime_cost_pct':            prime_pct,
        'flag_over_62':              prime_pct > 62.0,
        'sales_per_labor_hour_by_dow': dow_out,
        'data_gap':                  None if total_labor > 0 else 'no labor entries — add labor data to enable prime cost',
    }


def create_labor_entry(db: Session, restaurant_id: str, data: dict) -> LaborEntry:
    entry = LaborEntry(
        restaurant_id = _to_uuid(restaurant_id),
        business_date = data['business_date'],
        hours         = Decimal(str(data['hours'])),
        labor_cost    = Decimal(str(data['labor_cost'])),
        role          = data.get('role'),
        source        = data.get('source', 'manual'),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
