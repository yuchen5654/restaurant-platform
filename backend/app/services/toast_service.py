from datetime import datetime, timedelta

import httpx

TOAST_BASE = 'https://ws-sandbox-api.eng.toasttab.com'  # swap for prod URL in settings


async def get_toast_token(client_id: str, client_secret: str) -> str:
    async with httpx.AsyncClient() as c:
        resp = await c.post(
            f'{TOAST_BASE}/authentication/v1/authentication/login',
            json={
                'clientId':       client_id,
                'clientSecret':   client_secret,
                'userAccessType': 'TOAST_MACHINE_CLIENT',
            },
        )
        resp.raise_for_status()
        return resp.json()['token']['accessToken']


async def fetch_toast_orders(token: str, location_guid: str, date: datetime) -> list:
    start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end   = start + timedelta(days=1)
    async with httpx.AsyncClient() as c:
        resp = await c.get(
            f'{TOAST_BASE}/orders/v2/orders',
            headers={
                'Authorization':               f'Bearer {token}',
                'Toast-Restaurant-External-ID': location_guid,
            },
            params={
                'startDate': start.strftime('%Y-%m-%dT%H:%M:%S.000+0000'),
                'endDate':   end.strftime('%Y-%m-%dT%H:%M:%S.000+0000'),
                'pageSize':  100,
            },
        )
        resp.raise_for_status()
        return resp.json()


def normalize_toast_orders(raw: list) -> list[dict]:
    """Collapse raw Toast orders into one {pos_name, quantity, revenue} row per unique item."""
    totals: dict[str, dict] = {}
    for order in raw:
        if order.get('voidDate'):
            continue
        for check in order.get('checks', []):
            for sel in check.get('selections', []):
                if sel.get('voided'):
                    continue
                name  = sel.get('displayName', 'Unknown')
                qty   = sel.get('quantity', 1)
                price = sel.get('price', 0) / 100 * qty  # Toast uses cents
                if name not in totals:
                    totals[name] = {'pos_name': name, 'quantity': 0, 'revenue': 0.0}
                totals[name]['quantity'] += qty
                totals[name]['revenue']  += price
    return list(totals.values())
