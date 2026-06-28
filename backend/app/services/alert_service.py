import logging
import uuid as _uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.alerts import Alert
from app.models.inventory import Ingredient
from app.models.sales import SalesByItem

logger = logging.getLogger(__name__)

SPIKE_THRESHOLD_PP = 5.0   # percentage points above trailing average


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


# ---------------------------------------------------------------------------
# Individual alert checkers
# ---------------------------------------------------------------------------

def check_food_cost_spike(db: Session, restaurant_id: str, today: datetime) -> dict | None:
    """Return an alert dict if today's food cost % is >5pp above the 30-day trailing average."""
    rid = _to_uuid(restaurant_id)

    def fc_pct(start: datetime, end: datetime) -> float | None:
        row = db.execute(
            select(
                func.sum(SalesByItem.gross_revenue).label('rev'),
                func.sum(SalesByItem.food_cost).label('fc'),
            ).where(
                SalesByItem.restaurant_id == rid,
                SalesByItem.business_date >= start,
                SalesByItem.business_date < end,
                SalesByItem.menu_item_id.is_not(None),
            )
        ).one()
        if row.rev and float(row.rev) > 0:
            return float(row.fc or 0) / float(row.rev) * 100
        return None

    day_start  = today.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    today_pct  = fc_pct(day_start, day_start + timedelta(days=1))
    trail_pct  = fc_pct(day_start - timedelta(days=30), day_start)

    if today_pct is None or trail_pct is None:
        return None

    delta = today_pct - trail_pct
    if delta >= SPIKE_THRESHOLD_PP:
        return {
            'type':     'food_cost_spike',
            'severity': 'high',
            'message':  (
                f'Food cost today is {today_pct:.1f}% — '
                f'{delta:.1f}pp above your 30-day average of {trail_pct:.1f}%. '
                f'Check receiving and waste logs.'
            ),
        }
    return None


def check_low_stock(db: Session, restaurant_id: str) -> list[dict]:
    """Return one alert dict per ingredient at or below its par level."""
    rid = _to_uuid(restaurant_id)
    low = (
        db.query(Ingredient)
        .filter(
            Ingredient.restaurant_id == rid,
            Ingredient.par_level.is_not(None),
            Ingredient.current_stock <= Ingredient.par_level,
        )
        .all()
    )
    return [
        {
            'type':          'low_stock',
            'severity':      'medium',
            'message':       (
                f'{i.name} at {float(i.current_stock):.2f} {i.unit} — '
                f'below par of {float(i.par_level):.2f}. '
                f'Reorder: {float(i.reorder_qty or 0):.2f} {i.unit}.'
            ),
            'ingredient_id': str(i.id),
        }
        for i in low
    ]


def check_inventory_variance(db: Session, restaurant_id: str, date: datetime) -> list[dict]:
    """Theoretical usage (depletion) vs actual count variance.
    >15% unexplained gap = potential theft or portioning issue.
    Implement after inventory count flow is live (Step 5B data accumulates)."""
    return []


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def store_alerts(db: Session, restaurant_id: str, alerts: list[dict]) -> list[Alert]:
    """Persist alert dicts to the alerts table and return the saved rows."""
    rid    = _to_uuid(restaurant_id)
    saved  = []
    for a in alerts:
        extra = {k: v for k, v in a.items() if k not in ('type', 'severity', 'message')}
        row   = Alert(
            restaurant_id = rid,
            alert_type    = a['type'],
            severity      = a['severity'],
            message       = a['message'],
            extra_data    = extra or None,
        )
        db.add(row)
        saved.append(row)
        logger.info('[%s] alert stored: %s', a['severity'].upper(), a['message'])
    db.commit()
    return saved


# ---------------------------------------------------------------------------
# Convenience: run all checks for one restaurant and persist results
# ---------------------------------------------------------------------------

def run_alerts_for_restaurant(db: Session, restaurant_id: str, today: datetime) -> list[dict]:
    alerts: list[dict] = []
    spike = check_food_cost_spike(db, restaurant_id, today)
    if spike:
        alerts.append(spike)
    alerts.extend(check_low_stock(db, restaurant_id))
    alerts.extend(check_inventory_variance(db, restaurant_id, today))
    if alerts:
        store_alerts(db, restaurant_id, alerts)
    return alerts
