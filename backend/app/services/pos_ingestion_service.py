import logging
import uuid as _uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.sales import PosItemMapping, SalesByItem
from app.services.depletion_service import deplete_from_sale

logger = logging.getLogger(__name__)


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


async def ingest_toast_day(
    db: Session,
    restaurant_id: str,
    location_guid: str,
    client_id: str,
    client_secret: str,
    business_date: datetime,
) -> dict:
    from app.services.toast_service import (
        fetch_toast_orders,
        get_toast_token,
        normalize_toast_orders,
    )

    token      = await get_toast_token(client_id, client_secret)
    raw        = await fetch_toast_orders(token, location_guid, business_date)
    normalized = normalize_toast_orders(raw)

    return _process_normalized(db, restaurant_id, normalized, business_date)


def _process_normalized(
    db: Session,
    restaurant_id: str,
    normalized: list[dict],
    business_date: datetime,
) -> dict:
    """Apply mapping + depletion logic to a list of already-normalised POS items."""
    rid = _to_uuid(restaurant_id)
    mapped = 0
    unmapped = 0

    for item in normalized:
        mapping = (
            db.query(PosItemMapping)
            .filter(
                PosItemMapping.restaurant_id == rid,
                PosItemMapping.pos_item_name == item['pos_name'],
            )
            .first()
        )

        if mapping and mapping.is_ignored:
            continue

        if mapping and mapping.menu_item_id:
            deplete_from_sale(
                db, restaurant_id,
                str(mapping.menu_item_id),
                item['quantity'], business_date, item['revenue'],
            )
            mapped += item['quantity']
        else:
            db.add(SalesByItem(
                restaurant_id = rid,
                business_date = business_date,
                raw_pos_name  = item['pos_name'],
                quantity_sold = item['quantity'],
                gross_revenue = item['revenue'],
            ))
            unmapped += 1

    db.commit()
    logger.info(
        'Toast ingest complete — mapped: %d items, unmapped: %d items',
        mapped, unmapped,
    )
    return {'mapped': mapped, 'unmapped': unmapped}
