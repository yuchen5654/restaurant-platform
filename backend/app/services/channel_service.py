from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.adjustments import ChannelFee
from app.models.sales import SalesByItem
import uuid as _uuid


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_channel_profitability(db: Session, restaurant_id: str, window_days: int = 28) -> list[dict]:
    rid   = _to_uuid(restaurant_id)
    since = _now() - timedelta(days=window_days)

    fee_rows = db.execute(
        select(ChannelFee).where(ChannelFee.restaurant_id == rid)
    ).scalars().all()
    fees = {f.channel: float(f.commission_rate) for f in fee_rows}

    agg_rows = db.execute(
        select(
            SalesByItem.channel,
            func.count(SalesByItem.id).label('order_count'),
            func.coalesce(func.sum(SalesByItem.gross_revenue), 0).label('revenue'),
            func.coalesce(func.sum(SalesByItem.food_cost), 0).label('food_cost'),
        )
        .where(
            SalesByItem.restaurant_id == rid,
            SalesByItem.business_date >= since,
            SalesByItem.channel.is_not(None),
        )
        .group_by(SalesByItem.channel)
    ).all()

    rows = []
    for s in agg_rows:
        channel         = s.channel or 'unknown'
        revenue         = float(s.revenue or 0)
        food_cost       = float(s.food_cost or 0)
        commission_rate = fees.get(channel, 0.0)
        commission      = revenue * commission_rate
        net             = revenue - food_cost - commission
        order_count     = int(s.order_count or 0)
        per_order_net   = net / order_count if order_count > 0 else 0.0

        action = None
        if net < 0:
            action = (
                f'{channel} channel is unprofitable — net ${net:.2f} over {window_days}d; '
                f'review commission rate or channel pricing'
            )

        rows.append({
            'channel':          channel,
            'revenue':          round(revenue, 2),
            'food_cost':        round(food_cost, 2),
            'commission':       round(commission, 2),
            'net_contribution': round(net, 2),
            'per_order_net':    round(per_order_net, 2),
            'action':           action,
        })

    rows.sort(key=lambda r: r['net_contribution'], reverse=True)
    return rows


def get_channel_fees(db: Session, restaurant_id: str) -> list[ChannelFee]:
    rid = _to_uuid(restaurant_id)
    return db.execute(
        select(ChannelFee).where(ChannelFee.restaurant_id == rid)
    ).scalars().all()


def create_channel_fee(db: Session, restaurant_id: str, channel: str, commission_rate: float) -> ChannelFee:
    rid = _to_uuid(restaurant_id)
    fee = ChannelFee(
        restaurant_id   = rid,
        channel         = channel,
        commission_rate = Decimal(str(commission_rate)),
    )
    db.add(fee)
    db.commit()
    db.refresh(fee)
    return fee


def update_channel_fee(db: Session, restaurant_id: str, fee_id: str, commission_rate: float) -> ChannelFee | None:
    rid = _to_uuid(restaurant_id)
    fee = db.get(ChannelFee, _to_uuid(fee_id))
    if not fee or fee.restaurant_id != rid:
        return None
    fee.commission_rate = Decimal(str(commission_rate))
    db.commit()
    db.refresh(fee)
    return fee
