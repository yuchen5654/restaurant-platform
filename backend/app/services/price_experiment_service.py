"""
Price test-and-learn: auto-logs MenuPriceEvent on any menu_item price change,
then analyses before/after metrics for events older than 14 days.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.price_events import MenuPriceEvent
from app.models.recipe import MenuItem
from app.models.sales import SalesByItem

# Verdict string constants — import these in any service that pattern-matches verdicts
# so a wording change here doesn't silently break downstream logic.
VERDICT_MAINTAINED    = 'price change maintained or improved margin'
VERDICT_VOLUME_DROP   = 'volume dropped significantly — consider reverting'
VERDICT_DECLINED      = 'margin declined — monitor'
VERDICT_INSUFFICIENT  = 'insufficient data'
VERDICT_ITEM_DELETED  = 'item no longer active'


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_tz(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def log_price_event(
    db: Session,
    restaurant_id: str,
    menu_item_id: str,
    old_price: Decimal,
    new_price: Decimal,
) -> MenuPriceEvent:
    # flush only — caller (the PATCH handler) owns the transaction and commits after
    # updating the menu item. This keeps the event and the price change atomic.
    event = MenuPriceEvent(
        restaurant_id=_to_uuid(restaurant_id),
        menu_item_id=_to_uuid(menu_item_id),
        old_price=old_price,
        new_price=new_price,
    )
    db.add(event)
    db.flush()
    return event


def get_price_experiments(db: Session, restaurant_id: str) -> list[dict]:
    rid     = _to_uuid(restaurant_id)
    now     = _now()
    cutoff  = now - timedelta(days=14)   # only analyse events old enough for after-data

    events = db.execute(
        select(MenuPriceEvent)
        .where(
            MenuPriceEvent.restaurant_id == rid,
            MenuPriceEvent.changed_at <= cutoff,
        )
        .order_by(MenuPriceEvent.menu_item_id, MenuPriceEvent.changed_at)
    ).scalars().all()

    rows = []
    for event in events:
        item = db.get(MenuItem, event.menu_item_id)
        # Skip true cross-tenant rows (item belongs to another restaurant).
        # Emit a placeholder when the item was deleted (hard- or soft-deleted) after the
        # price event was recorded.  Hard deletes are prevented by the FK, so in practice
        # this triggers on is_active=False (soft delete).
        if item is not None and item.restaurant_id != rid:
            continue
        if item is None or not item.is_active:
            rows.append({
                'event_id':              str(event.id),
                'menu_item_id':          str(event.menu_item_id),
                'item_name':             '[deleted item]',
                'old_price':             float(event.old_price),
                'new_price':             float(event.new_price),
                'price_change_pct':      None,
                'changed_at':            event.changed_at.isoformat(),
                'before_days':           None,
                'after_days':            None,
                'before_units_per_day':  None,
                'after_units_per_day':   None,
                'units_delta_pct':       None,
                'before_margin_per_day': None,
                'after_margin_per_day':  None,
                'margin_delta_pct':      None,
                'verdict':               VERDICT_ITEM_DELETED,
            })
            continue

        changed_at = _ensure_tz(event.changed_at)

        # Before window: up to 28d before the event, clamped by any prior event on same item
        prior = db.execute(
            select(MenuPriceEvent)
            .where(
                MenuPriceEvent.restaurant_id == rid,
                MenuPriceEvent.menu_item_id  == event.menu_item_id,
                MenuPriceEvent.changed_at    < changed_at,
            )
            .order_by(MenuPriceEvent.changed_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        before_start = (
            max(_ensure_tz(prior.changed_at), changed_at - timedelta(days=28))
            if prior else changed_at - timedelta(days=28)
        )
        before_end = changed_at

        # After window: up to 28d after the event, clamped by next event
        nxt = db.execute(
            select(MenuPriceEvent)
            .where(
                MenuPriceEvent.restaurant_id == rid,
                MenuPriceEvent.menu_item_id  == event.menu_item_id,
                MenuPriceEvent.changed_at    > changed_at,
            )
            .order_by(MenuPriceEvent.changed_at)
            .limit(1)
        ).scalar_one_or_none()

        after_end = (
            min(_ensure_tz(nxt.changed_at), now)
            if nxt else min(changed_at + timedelta(days=28), now)
        )
        after_start = changed_at

        def _window_metrics(start: datetime, end: datetime) -> dict:
            days = max((end - start).days, 1)
            row  = db.execute(
                select(
                    func.coalesce(func.sum(SalesByItem.quantity_sold), 0).label('units'),
                    func.coalesce(func.sum(SalesByItem.gross_revenue), 0).label('rev'),
                    func.coalesce(func.sum(SalesByItem.food_cost),     0).label('fc'),
                )
                .where(
                    SalesByItem.restaurant_id == rid,
                    SalesByItem.menu_item_id  == event.menu_item_id,
                    # Compare date columns directly to avoid UTC-vs-naive timezone mismatch
                    SalesByItem.business_date >= start.date(),
                    SalesByItem.business_date <  end.date(),
                )
            ).one()
            units  = int(row.units)
            margin = float(row.rev) - float(row.fc)
            return {
                'units_per_day':  round(units  / days, 3),
                'margin_per_day': round(margin / days, 2),
                'days':           days,
            }

        before = _window_metrics(before_start, before_end)
        after  = _window_metrics(after_start,  after_end)

        old_p = float(event.old_price)
        new_p = float(event.new_price)
        price_change_pct = round((new_p - old_p) / old_p * 100, 1) if old_p != 0 else None

        units_delta_pct = (
            round((after['units_per_day'] - before['units_per_day']) / before['units_per_day'] * 100, 1)
            if before['units_per_day'] > 0 else None
        )
        margin_delta_pct = (
            round((after['margin_per_day'] - before['margin_per_day']) / abs(before['margin_per_day']) * 100, 1)
            if before['margin_per_day'] != 0 else None
        )

        if units_delta_pct is None or margin_delta_pct is None:
            verdict = VERDICT_INSUFFICIENT
        elif margin_delta_pct >= 0:
            verdict = VERDICT_MAINTAINED
        elif units_delta_pct < -15:
            verdict = VERDICT_VOLUME_DROP
        else:
            verdict = VERDICT_DECLINED

        rows.append({
            'event_id':              str(event.id),
            'menu_item_id':          str(event.menu_item_id),
            'item_name':             item.name,
            'old_price':             old_p,
            'new_price':             new_p,
            'price_change_pct':      price_change_pct,
            'changed_at':            event.changed_at.isoformat(),
            'before_days':           before['days'],
            'after_days':            after['days'],
            'before_units_per_day':  before['units_per_day'],
            'after_units_per_day':   after['units_per_day'],
            'units_delta_pct':       units_delta_pct,
            'before_margin_per_day': before['margin_per_day'],
            'after_margin_per_day':  after['margin_per_day'],
            'margin_delta_pct':      margin_delta_pct,
            'verdict':               verdict,
        })

    return rows
