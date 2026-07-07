import logging
import uuid as _uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.adjustments import SaleAdjustment
from app.models.alerts import Alert
from app.models.inventory import Ingredient, InvoiceLineItem, VendorInvoice
from app.models.recipe import MenuItem
from app.models.sales import SalesByItem

logger = logging.getLogger(__name__)

SPIKE_THRESHOLD_PP = 5.0   # percentage points above trailing average


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


# ---------------------------------------------------------------------------
# Alert explanation builder
# ---------------------------------------------------------------------------

def _build_explanation(
    db: Session, rid: _uuid.UUID, day_start: datetime, trail_pct: float
) -> dict:
    """Build three-driver explanation for a food cost spike."""
    since30 = day_start - timedelta(days=30)
    day_end = day_start + timedelta(days=1)

    # Driver 1 — price-inflated ingredients
    # Compare last-7d avg invoice cost vs prior-23d avg; flag >10% rise
    ingredients = db.execute(
        select(Ingredient).where(Ingredient.restaurant_id == rid)
    ).scalars().all()

    price_drivers: list[dict] = []
    for ing in ingredients:
        iid     = ing.id
        recent  = db.execute(
            select(func.avg(InvoiceLineItem.unit_cost))
            .join(VendorInvoice, InvoiceLineItem.invoice_id == VendorInvoice.id)
            .where(
                VendorInvoice.restaurant_id == rid,
                InvoiceLineItem.ingredient_id == iid,
                VendorInvoice.received_at >= day_start - timedelta(days=7),
                VendorInvoice.received_at <  day_end,
            )
        ).scalar()
        hist = db.execute(
            select(func.avg(InvoiceLineItem.unit_cost))
            .join(VendorInvoice, InvoiceLineItem.invoice_id == VendorInvoice.id)
            .where(
                VendorInvoice.restaurant_id == rid,
                InvoiceLineItem.ingredient_id == iid,
                VendorInvoice.received_at >= since30,
                VendorInvoice.received_at <  day_start - timedelta(days=7),
            )
        ).scalar()
        if recent and hist and float(hist) > 0:
            chg = (float(recent) - float(hist)) / float(hist) * 100
            if chg > 10:
                price_drivers.append({'ingredient': ing.name, 'pct_change': round(chg, 1)})

    price_drivers.sort(key=lambda x: x['pct_change'], reverse=True)

    # Driver 2 — mix shift: items sold today whose FC% is >10pp above trailing avg
    today_sales = db.execute(
        select(SalesByItem).where(
            SalesByItem.restaurant_id == rid,
            SalesByItem.business_date >= day_start,
            SalesByItem.business_date <  day_end,
            SalesByItem.menu_item_id.is_not(None),
        )
    ).scalars().all()

    mix_drivers: list[dict] = []
    for s in today_sales:
        rev = float(s.gross_revenue or 0)
        if rev > 0:
            item_fc_pct = float(s.food_cost or 0) / rev * 100
            if item_fc_pct > trail_pct + 10:
                item = db.get(MenuItem, s.menu_item_id)
                if item:
                    mix_drivers.append({'item': item.name, 'fc_pct': round(item_fc_pct, 1)})

    mix_drivers.sort(key=lambda x: x['fc_pct'], reverse=True)

    # Driver 3 — adjustment spike today vs 30d daily avg
    today_adj = float(db.execute(
        select(func.coalesce(func.sum(SaleAdjustment.amount), 0))
        .where(
            SaleAdjustment.restaurant_id == rid,
            SaleAdjustment.business_date >= day_start,
            SaleAdjustment.business_date <  day_end,
        )
    ).scalar() or 0)

    daily_adj_avg = float(db.execute(
        select(func.coalesce(func.sum(SaleAdjustment.amount), 0))
        .where(
            SaleAdjustment.restaurant_id == rid,
            SaleAdjustment.business_date >= since30,
            SaleAdjustment.business_date <  day_start,
        )
    ).scalar() or 0) / 30.0

    adj_driver = None
    if today_adj > daily_adj_avg * 2 and today_adj > 50:
        adj_driver = {
            'today_total': round(today_adj, 2),
            'daily_avg':   round(daily_adj_avg, 2),
        }

    return {
        'price_drivers': price_drivers[:3],
        'mix_drivers':   mix_drivers[:3],
        'adj_driver':    adj_driver,
    }


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
        explanation = _build_explanation(db, rid, day_start, trail_pct)
        return {
            'type':        'food_cost_spike',
            'severity':    'high',
            'message':     (
                f'Food cost today is {today_pct:.1f}% — '
                f'{delta:.1f}pp above your 30-day average of {trail_pct:.1f}%. '
                f'Check receiving and waste logs.'
            ),
            'explanation': explanation,
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
