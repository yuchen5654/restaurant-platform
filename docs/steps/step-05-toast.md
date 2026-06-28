# Step 5 — Toast POS Integration

**Estimated time:** 8–12 hours
**Phase:** 1 (Foundation)
**Depends on:** Step 4.

---

## Goal

Automated nightly pipeline pulling sales from Toast's API, mapping POS item names to recipe-engine menu items, running depletion for each mapped sale, and flagging unmapped items for one-time operator review. This makes the platform generate value passively — no daily input required.

## 5.1 Toast client — `app/services/toast_service.py`

```python
import httpx
from datetime import datetime, timedelta

TOAST_BASE = 'https://ws-sandbox-api.eng.toasttab.com'  # swap for prod URL

async def get_toast_token(client_id: str, client_secret: str) -> str:
    async with httpx.AsyncClient() as c:
        resp = await c.post(f'{TOAST_BASE}/authentication/v1/authentication/login',
            json={'clientId':client_id,'clientSecret':client_secret,
                  'userAccessType':'TOAST_MACHINE_CLIENT'})
        resp.raise_for_status()
        return resp.json()['token']['accessToken']

async def fetch_toast_orders(token: str, location_guid: str, date: datetime) -> list:
    start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end   = start + timedelta(days=1)
    async with httpx.AsyncClient() as c:
        resp = await c.get(f'{TOAST_BASE}/orders/v2/orders',
            headers={'Authorization': f'Bearer {token}',
                     'Toast-Restaurant-External-ID': location_guid},
            params={'startDate': start.strftime('%Y-%m-%dT%H:%M:%S.000+0000'),
                    'endDate':   end.strftime('%Y-%m-%dT%H:%M:%S.000+0000'),
                    'pageSize':  100})
        resp.raise_for_status()
        return resp.json()

def normalize_toast_orders(raw: list) -> list[dict]:
    """Collapse raw orders into {pos_name, quantity, revenue} per unique item."""
    totals: dict[str, dict] = {}
    for order in raw:
        if order.get('voidDate'): continue
        for check in order.get('checks', []):
            for sel in check.get('selections', []):
                if sel.get('voided'): continue
                name  = sel.get('displayName','Unknown')
                qty   = sel.get('quantity', 1)
                price = sel.get('price', 0) / 100 * qty  # Toast uses cents
                if name not in totals:
                    totals[name] = {'pos_name':name,'quantity':0,'revenue':0.0}
                totals[name]['quantity'] += qty
                totals[name]['revenue']  += price
    return list(totals.values())
```

## 5.2 Ingestion pipeline — `app/services/pos_ingestion_service.py`

```python
from sqlalchemy.orm import Session
from app.models.sales import PosItemMapping, SalesByItem
from app.services.depletion_service import deplete_from_sale
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def ingest_toast_day(db: Session, restaurant_id: str, location_guid: str,
                            client_id: str, client_secret: str, business_date: datetime):
    from app.services.toast_service import get_toast_token, fetch_toast_orders, normalize_toast_orders
    token      = await get_toast_token(client_id, client_secret)
    raw        = await fetch_toast_orders(token, location_guid, business_date)
    normalized = normalize_toast_orders(raw)

    mapped=0; unmapped=0
    for item in normalized:
        mapping = db.query(PosItemMapping).filter(
            PosItemMapping.restaurant_id == restaurant_id,
            PosItemMapping.pos_item_name == item['pos_name'],
        ).first()
        if mapping and mapping.is_ignored: continue
        if mapping and mapping.menu_item_id:
            deplete_from_sale(db, restaurant_id, str(mapping.menu_item_id),
                              item['quantity'], business_date, item['revenue'])
            mapped += item['quantity']
        else:
            db.add(SalesByItem(restaurant_id=restaurant_id, business_date=business_date,
                               raw_pos_name=item['pos_name'], quantity_sold=item['quantity'],
                               gross_revenue=item['revenue']))
            unmapped += 1
    db.commit()
    logger.info(f'Toast ingest complete — mapped:{mapped} unmapped:{unmapped}')
    return {'mapped': mapped, 'unmapped': unmapped}
```

## 5.3 Nightly Celery task — `app/workers/`

```python
# app/workers/celery_app.py
from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery('restaurant_platform', broker=settings.REDIS_URL)
celery_app.conf.beat_schedule = {
    'pull-toast-daily': {
        'task':     'app.workers.tasks.pull_all_toast_restaurants',
        'schedule': crontab(hour=3, minute=0),
    },
    'run-nightly-alerts': {
        'task':     'app.workers.tasks.run_nightly_alerts',
        'schedule': crontab(hour=3, minute=30),
    },
}

# app/workers/tasks.py
from app.workers.celery_app import celery_app
from app.database import SessionLocal
from app.models.restaurant import Restaurant
from app.services.pos_ingestion_service import ingest_toast_day
from datetime import datetime, timezone, timedelta
import asyncio

@celery_app.task
def pull_all_toast_restaurants():
    db = SessionLocal()
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    try:
        for r in db.query(Restaurant).filter(
            Restaurant.toast_location_guid.is_not(None), Restaurant.is_active==True
        ).all():
            asyncio.run(ingest_toast_day(
                db, str(r.id), r.toast_location_guid,
                'YOUR_TOAST_CLIENT_ID',     # load from Secrets Manager in production
                'YOUR_TOAST_SECRET',
                yesterday,
            ))
    finally:
        db.close()
```

Start workers:
```bash
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info
```

---

## Notes

- **Square** follows the identical pattern. Add a parallel `ingest_square_day` and a `square_location_id` check. Square's API is similarly well-documented and OAuth2-based.
- Unmapped items stored with `raw_pos_name` surface in the dashboard for the operator to map once via the `PosItemMapping` table. After mapping, they're automatic forever.
- Use the Toast **sandbox** URL during development; switch to the production URL only when going live.

## Done when

You can run `ingest_toast_day` against the Toast sandbox (or a mocked order payload) and verify mapped items trigger depletion while unmapped items are stored with `raw_pos_name`.

## Then

Update checkbox in `CLAUDE.md`, `git commit`, move to `step-05b-ingestion.md`.
