"""
Daily action list: priority-ordered, deduped, capped at 7.
Draws from all existing insights (variance, pars, prime cost, channels,
price experiments, adjustments, menu engineering Dogs).
"""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alerts import Alert

logger = logging.getLogger(__name__)


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


_MAX_ACTIONS = 7
_EMPTY_MSG   = 'No actions needed — all metrics in range.'


def get_daily_actions(db: Session, restaurant_id: str) -> list[dict]:
    from app.services.insights_service    import get_variance_report, get_par_recommendations, get_menu_engineering
    from app.services.channel_service     import get_channel_profitability
    from app.services.labor_service       import get_prime_cost
    from app.services.price_experiment_service import get_price_experiments, VERDICT_VOLUME_DROP

    rid     = _to_uuid(restaurant_id)
    actions: list[dict] = []

    # 1. Unread high-severity alerts
    unread_high = db.execute(
        select(Alert)
        .where(
            Alert.restaurant_id == rid,
            Alert.severity      == 'high',
            Alert.is_read.is_(False),
        )
        .order_by(Alert.created_at.desc())
        .limit(3)
    ).scalars().all()

    for a in unread_high:
        explanation = (a.extra_data or {}).get('explanation')
        text = a.message
        if explanation:
            drivers = []
            for d in (explanation.get('price_drivers') or [])[:2]:
                drivers.append(f"{d['ingredient']} +{d['pct_change']}%")
            for d in (explanation.get('mix_drivers') or [])[:1]:
                drivers.append(f"{d['item']} FC {d['fc_pct']}%")
            if drivers:
                text = f'{a.message} Likely drivers: {", ".join(drivers)}.'
        actions.append({
            'severity':       'high',
            'text':           text,
            'source_insight': 'alerts',
            'link_route':     '/insights',
        })

    # 2. Variance over threshold
    try:
        variance = get_variance_report(db, restaurant_id, window_days=7)
        flagged  = [r for r in variance if r.get('recommended_action') and not r.get('data_gap')]
        if flagged:
            total_val = sum(abs(r['variance_value'] or 0) for r in flagged)
            actions.append({
                'severity':       'high' if total_val > 200 else 'medium',
                'text': (
                    f'{len(flagged)} ingredient(s) with unexplained variance '
                    f'(${total_val:.0f} total) — check portioning and waste logs'
                ),
                'source_insight': 'variance',
                'link_route':     '/insights?tab=variance',
            })
    except Exception:
        logger.exception('daily-actions: variance check failed')

    # 3. Par stockout risks (< 2 days cover)
    try:
        pars = get_par_recommendations(db, restaurant_id)
        at_risk = [
            r for r in pars
            if not r.get('data_gap')
            and r.get('cover_days') is not None
            and r['cover_days'] < 2
        ]
        if at_risk:
            names = ', '.join(r['ingredient_name'] for r in at_risk[:3])
            suffix = f' (+{len(at_risk)-3} more)' if len(at_risk) > 3 else ''
            actions.append({
                'severity':       'high',
                'text':           f'Reorder needed: {names}{suffix} — less than 2 days cover',
                'source_insight': 'pars',
                'link_route':     '/insights?tab=pars',
            })
    except Exception:
        logger.exception('daily-actions: pars check failed')

    # 4. Losing channels
    try:
        channels = get_channel_profitability(db, restaurant_id, window_days=28)
        losing   = [c for c in channels if c['net_contribution'] < 0]
        if losing:
            ch_names = ', '.join(c['channel'] for c in losing)
            actions.append({
                'severity':       'medium',
                'text':           f'Unprofitable channel(s): {ch_names} — review commission rates or pricing',
                'source_insight': 'channel',
                'link_route':     '/insights?tab=channel',
            })
    except Exception:
        logger.exception('daily-actions: channel check failed')

    # 5. Price experiment — volume dropped
    try:
        experiments = get_price_experiments(db, restaurant_id)
        risky = [e for e in experiments if e['verdict'] == VERDICT_VOLUME_DROP]
        if risky:
            names = ', '.join(e['item_name'] for e in risky[:2])
            actions.append({
                'severity':       'medium',
                'text':           f'Price change may be hurting volume: {names} — review price experiments',
                'source_insight': 'price-experiments',
                'link_route':     '/insights?tab=price-experiments',
            })
    except Exception:
        logger.exception('daily-actions: price-experiments check failed')

    # 6. Prime cost over 62%
    try:
        prime = get_prime_cost(db, restaurant_id, window_days=28)
        if prime.get('flag_over_62') and prime.get('prime_cost_pct') is not None:
            actions.append({
                'severity':       'medium',
                'text': (
                    f'Prime cost {prime["prime_cost_pct"]:.1f}% — above 62% target; '
                    f'review labor scheduling and food cost'
                ),
                'source_insight': 'prime-cost',
                'link_route':     '/insights?tab=prime-cost',
            })
    except Exception:
        logger.exception('daily-actions: prime-cost check failed')

    # 7. Menu-engineering Dogs (60d window)
    # TODO: When Step 8 forecasting is live, surface prep/order suggestions here too.
    try:
        eng  = get_menu_engineering(db, restaurant_id, window_days=60)
        dogs = [i for i in eng.get('items', []) if i['quadrant'] == 'Dog']
        if dogs:
            names = ', '.join(d['name'] for d in dogs[:3])
            suffix = f' (+{len(dogs)-3} more)' if len(dogs) > 3 else ''
            actions.append({
                'severity':       'low',
                'text':           f'Low-performing items (60d): {names}{suffix} — cut or reposition',
                'source_insight': 'menu-eng',
                'link_route':     '/insights?tab=menu-eng',
            })
    except Exception:
        logger.exception('daily-actions: menu-eng check failed')

    # Dedup by source_insight (keep first occurrence, which is highest priority)
    seen: set[str] = set()
    deduped: list[dict] = []
    for a in actions:
        key = a['source_insight']
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    return deduped[:_MAX_ACTIONS]
