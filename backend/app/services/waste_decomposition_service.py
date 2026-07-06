from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inventory import WasteLog, Ingredient
import uuid as _uuid

# Map raw WasteLog.reason values to output categories
_REASON_BUCKET = {
    'spoilage':    'spoilage',
    'prep_waste':  'prep',
    'over_portion':'prep',
    'dropped':     'plate',
    'comp':        'error',
    'theft':       'error',
}

_ACTIONS = {
    'spoilage': 'review order quantities and storage — spoilage indicates over-purchasing or FIFO issues',
    'prep':     'check prep yields and portion guides — prep waste may signal training gap',
    'plate':    'track drop incidents by station; consider plating process review',
    'error':    'audit comps/theft by employee and daypart; set threshold alerts',
    'unclassified': 'classify waste reasons at point of logging to enable targeted action',
}


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


def get_waste_decomposition(db: Session, restaurant_id: str, window_days: int = 28) -> list[dict]:
    rid   = _to_uuid(restaurant_id)
    since = datetime.now(timezone.utc) - timedelta(days=window_days)

    waste_rows = db.execute(
        select(WasteLog).where(
            WasteLog.restaurant_id == rid,
            WasteLog.logged_at >= since,
        )
    ).scalars().all()

    buckets: dict[str, dict] = {}
    for w in waste_rows:
        bucket = _REASON_BUCKET.get(w.reason or '', 'unclassified')
        if bucket not in buckets:
            buckets[bucket] = {'waste_dollars': Decimal('0'), 'waste_qty': Decimal('0')}

        qty = w.quantity or Decimal('0')
        if w.cost_at_time is not None:
            dollars = qty * w.cost_at_time
        else:
            # Fall back to current ingredient cost
            ing = db.get(Ingredient, w.ingredient_id)
            dollars = qty * (ing.current_cost_per_unit or Decimal('0')) if ing else Decimal('0')

        buckets[bucket]['waste_dollars'] += dollars
        buckets[bucket]['waste_qty']     += qty

    rows = []
    for reason, agg in sorted(buckets.items(), key=lambda x: x[1]['waste_dollars'], reverse=True):
        dollars = float(agg['waste_dollars'])
        qty     = float(agg['waste_qty'])
        rows.append({
            'reason':             reason,
            'waste_dollars':      round(dollars, 2),
            'waste_qty':          round(qty, 4),
            'recommended_action': _ACTIONS.get(reason) if dollars > 0 else None,
        })

    return rows
