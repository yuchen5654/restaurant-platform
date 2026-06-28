# Step 6 — Alert Engine

**Estimated time:** 4–6 hours
**Phase:** 1 (Foundation)
**Depends on:** Step 5B.

---

## Goal

Rule-based alerts that fire when key metrics deviate. No ML — deliberate business rules catching the scenarios operators most need to know about: food cost spikes, low stock, inventory variance.

## `app/services/alert_service.py`

```python
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from app.models.sales import SalesByItem
from app.models.inventory import Ingredient
from app.models.restaurant import Restaurant
from datetime import datetime, timedelta, timezone

def check_food_cost_spike(db: Session, restaurant_id: str, today: datetime) -> dict | None:
    """Fires if today's food cost % is >5pp above 30-day trailing average."""
    spike_threshold = 5.0
    def fc_pct(start, end):
        r = db.execute(select(
            func.sum(SalesByItem.gross_revenue).label('rev'),
            func.sum(SalesByItem.food_cost).label('fc'),
        ).where(SalesByItem.restaurant_id==restaurant_id,
                SalesByItem.business_date>=start, SalesByItem.business_date<end,
                SalesByItem.menu_item_id.is_not(None))).one()
        if r.rev and float(r.rev)>0: return float(r.fc or 0)/float(r.rev)*100
        return None
    start = today.replace(hour=0,minute=0,second=0,microsecond=0,tzinfo=timezone.utc)
    today_pct = fc_pct(start, start+timedelta(days=1))
    trail_pct = fc_pct(start-timedelta(days=30), start)
    if today_pct is None or trail_pct is None: return None
    if today_pct - trail_pct >= spike_threshold:
        return {'type':'food_cost_spike','severity':'high',
                'message': f'Food cost today is {today_pct:.1f}% — '
                           f'{today_pct-trail_pct:.1f}pp above your 30-day average of {trail_pct:.1f}%. '
                           f'Check receiving and waste logs.'}
    return None

def check_low_stock(db: Session, restaurant_id: str) -> list[dict]:
    low = db.query(Ingredient).filter(
        Ingredient.restaurant_id == restaurant_id,
        Ingredient.par_level.is_not(None),
        Ingredient.current_stock <= Ingredient.par_level,
    ).all()
    return [{'type':'low_stock','severity':'medium',
             'message': f'{i.name} at {float(i.current_stock):.2f} {i.unit} — '
                        f'below par of {float(i.par_level):.2f}. '
                        f'Reorder: {float(i.reorder_qty or 0):.2f} {i.unit}.',
             'ingredient_id': str(i.id)} for i in low]

def check_inventory_variance(db: Session, restaurant_id: str, date: datetime) -> list[dict]:
    """Theoretical usage (depletion) vs actual count variance.
    >15% unexplained gap = potential theft or portioning issue.
    Implement after inventory count flow is live."""
    pass
```

Add to Celery (`app/workers/tasks.py`) — runs 3:30am after the POS pull:

```python
@celery_app.task
def run_nightly_alerts():
    from app.services.alert_service import check_food_cost_spike, check_low_stock
    db = SessionLocal()
    today = datetime.now(timezone.utc)
    try:
        for r in db.query(Restaurant).filter(Restaurant.is_active==True).all():
            alerts = []
            spike = check_food_cost_spike(db, str(r.id), today)
            if spike: alerts.append(spike)
            alerts.extend(check_low_stock(db, str(r.id)))
            # Store in DB for dashboard feed; send email/SMS via SendGrid/Twilio
            if alerts:
                store_alerts(db, str(r.id), alerts)  # you implement: persist + notify
    finally:
        db.close()
```

## Done when

You can manually trigger `check_food_cost_spike` and `check_low_stock` against seeded data and get correctly-formatted alert dicts.

## Then
Update checkbox, `git commit`, move to `step-07-frontend.md`.
