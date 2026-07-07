"""
Insights Engine — Step 11.
All analyses are derived at query time; nothing is stored in a separate results table.
Every public function returns plain dicts/lists; the router wraps them in Pydantic schemas.
"""
from __future__ import annotations

import uuid as _uuid
import zoneinfo as _zoneinfo
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import exc as _sa_exc
from sqlalchemy import func, select, and_
from sqlalchemy.orm import Session

from app.models.restaurant import Restaurant

from app.models.adjustments import SaleAdjustment
from app.models.insights import RestaurantSettings
from app.models.inventory import (
    Ingredient, InventoryCount, VendorInvoice, InvoiceLineItem,
    WasteLog, DepletionEvent,
)
from app.models.recipe import MenuItem, RecipeLine
from app.models.sales import SalesByItem, SalesSummary
from app.models.weather import WeatherDay
from app.services.food_cost_service import get_food_cost_summary


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 11.1  Settings
# ---------------------------------------------------------------------------

def get_or_create_settings(db: Session, restaurant_id: str) -> RestaurantSettings:
    rid = _to_uuid(restaurant_id)
    row = db.execute(
        select(RestaurantSettings).where(RestaurantSettings.restaurant_id == rid)
    ).scalar_one_or_none()
    if row is None:
        try:
            row = RestaurantSettings(restaurant_id=rid)
            db.add(row)
            db.flush()   # caller owns the transaction; no commit here
        except _sa_exc.IntegrityError:
            # Concurrent first-request race: another session beat us; roll back the
            # failed insert and re-select the row that now exists.
            db.rollback()
            row = db.execute(
                select(RestaurantSettings).where(RestaurantSettings.restaurant_id == rid)
            ).scalar_one()
    return row


def update_settings(db: Session, restaurant_id: str, fields: dict) -> RestaurantSettings:
    row = get_or_create_settings(db, restaurant_id)
    for k, v in fields.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 11.2  Theoretical vs. Actual Variance
# ---------------------------------------------------------------------------

def get_variance_report(db: Session, restaurant_id: str, window_days: int = 7) -> list[dict]:
    rid = _to_uuid(restaurant_id)
    now = _now()
    window_start = now - timedelta(days=window_days)

    # All ingredients that have at least 1 count in the window or before it
    ingredients = db.execute(
        select(Ingredient).where(Ingredient.restaurant_id == rid)
    ).scalars().all()

    rows = []
    for ing in ingredients:
        iid = ing.id

        # Opening count: latest count with counted_at <= window_start
        opening_row = db.execute(
            select(InventoryCount)
            .where(
                InventoryCount.restaurant_id == rid,
                InventoryCount.ingredient_id == iid,
                InventoryCount.counted_at <= window_start,
            )
            .order_by(InventoryCount.counted_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        # Closing count: latest count with counted_at <= now (within window)
        closing_row = db.execute(
            select(InventoryCount)
            .where(
                InventoryCount.restaurant_id == rid,
                InventoryCount.ingredient_id == iid,
                InventoryCount.counted_at > window_start,
                InventoryCount.counted_at <= now,
            )
            .order_by(InventoryCount.counted_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if opening_row is None or closing_row is None:
            rows.append({
                'ingredient_id':      str(iid),
                'ingredient_name':    ing.name,
                'unit':               ing.unit,
                'theoretical_qty':    None,
                'actual_qty':         None,
                'variance_qty':       None,
                'variance_value':     None,
                'variance_pct':       None,
                'data_gap':           True,
                'recommended_action': None,
            })
            continue

        t_open = opening_row.counted_at
        t_close = closing_row.counted_at

        # Received between the two counts (invoice lines)
        received = db.execute(
            select(func.coalesce(func.sum(InvoiceLineItem.quantity_received), 0))
            .join(VendorInvoice, InvoiceLineItem.invoice_id == VendorInvoice.id)
            .where(
                VendorInvoice.restaurant_id == rid,
                InvoiceLineItem.ingredient_id == iid,
                VendorInvoice.received_at > t_open,
                VendorInvoice.received_at <= t_close,
            )
        ).scalar() or Decimal('0')

        # Theoretical usage from depletion log between the two counts
        theoretical = db.execute(
            select(func.coalesce(func.sum(DepletionEvent.quantity), 0))
            .where(
                DepletionEvent.restaurant_id == rid,
                DepletionEvent.ingredient_id == iid,
                DepletionEvent.depleted_at > t_open,
                DepletionEvent.depleted_at <= t_close,
            )
        ).scalar() or Decimal('0')

        opening_qty = opening_row.quantity
        closing_qty = closing_row.quantity

        actual_usage      = opening_qty + Decimal(str(received)) - closing_qty
        theoretical_usage = Decimal(str(theoretical))
        variance_qty      = actual_usage - theoretical_usage

        unit_cost     = ing.current_cost_per_unit or Decimal('0')
        variance_value = variance_qty * unit_cost

        theoretical_f = float(theoretical_usage)
        variance_f    = float(variance_qty)
        variance_val_f = float(variance_value)

        variance_pct = (
            round(variance_f / theoretical_f * 100, 2)
            if theoretical_f > 0 else None
        )

        threshold = max(10.0, theoretical_f * float(unit_cost) * 0.05)
        action = None
        if abs(variance_val_f) >= threshold:
            direction = 'unexplained loss' if variance_val_f > 0 else 'negative variance'
            action = (
                f'investigate: {abs(variance_f):.2f} {ing.unit} / '
                f'${abs(variance_val_f):.2f} of {ing.name} {direction} '
                f'this {"week" if window_days <= 7 else f"{window_days}d"} — '
                f'check portioning and waste logging'
            )

        rows.append({
            'ingredient_id':      str(iid),
            'ingredient_name':    ing.name,
            'unit':               ing.unit,
            'theoretical_qty':    round(theoretical_f, 4),
            'actual_qty':         round(float(actual_usage), 4),
            'variance_qty':       round(variance_f, 4),
            'variance_value':     round(variance_val_f, 2),
            'variance_pct':       variance_pct,
            'data_gap':           False,
            'recommended_action': action,
        })

    return rows


# ---------------------------------------------------------------------------
# 11.3  Contribution Margin
# ---------------------------------------------------------------------------

def get_contribution_margins(db: Session, restaurant_id: str, window_days: int = 28) -> list[dict]:
    rid = _to_uuid(restaurant_id)
    since = _now() - timedelta(days=window_days)

    sales_rows = db.execute(
        select(
            SalesByItem.menu_item_id,
            func.sum(SalesByItem.quantity_sold).label('units'),
            func.sum(SalesByItem.gross_revenue).label('rev'),
        )
        .where(
            SalesByItem.restaurant_id == rid,
            SalesByItem.business_date >= since,
            SalesByItem.menu_item_id.is_not(None),
        )
        .group_by(SalesByItem.menu_item_id)
    ).all()

    rows = []
    for s in sales_rows:
        item = db.get(MenuItem, s.menu_item_id)
        if not item or item.restaurant_id != rid:
            continue
        plate_cost     = float(item.theoretical_food_cost)
        price          = float(item.menu_price)
        margin_dollars = price - plate_cost
        units          = int(s.units or 0)
        rows.append({
            'menu_item_id':   str(item.id),
            'name':           item.name,
            'category':       item.category,
            'units_sold':     units,
            'price':          price,
            'plate_cost':     round(plate_cost, 4),
            'margin_dollars': round(margin_dollars, 4),
            'total_margin':   round(margin_dollars * units, 2),
        })

    rows.sort(key=lambda r: r['total_margin'], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# 11.4  Menu Engineering 2×2
# ---------------------------------------------------------------------------

def get_menu_engineering(db: Session, restaurant_id: str, window_days: int = 28) -> dict:
    settings = get_or_create_settings(db, restaurant_id)
    margins  = get_contribution_margins(db, restaurant_id, window_days)

    if not margins:
        return {'items': [], 'popularity_threshold': 0, 'margin_threshold': 0}

    total_units        = sum(r['units_sold'] for r in margins)
    item_count         = len(margins)
    pop_factor         = float(settings.menu_eng_popularity_factor)
    popularity_threshold = pop_factor * (total_units / item_count) if item_count else 0
    margin_threshold   = sum(r['margin_dollars'] for r in margins) / item_count

    quadrant_map = {
        (True,  True):  ('Star',      'protect & feature prominently'),
        (True,  False): ('Plowhorse', 're-portion or nudge price up to improve margin'),
        (False, True):  ('Puzzle',    'reposition on menu / improve description to drive traffic'),
        (False, False): ('Dog',       'candidate to cut or replace'),
    }

    items = []
    for r in margins:
        high_pop    = r['units_sold'] >= popularity_threshold
        high_margin = r['margin_dollars'] >= margin_threshold
        quadrant, action = quadrant_map[(high_pop, high_margin)]
        items.append({
            'menu_item_id':       r['menu_item_id'],
            'name':               r['name'],
            'category':           r['category'],
            'units_sold':         r['units_sold'],
            'margin_dollars':     r['margin_dollars'],
            'quadrant':           quadrant,
            'recommended_action': action,
        })

    return {
        'items':                items,
        'popularity_threshold': round(popularity_threshold, 2),
        'margin_threshold':     round(margin_threshold, 4),
    }


# ---------------------------------------------------------------------------
# 11.5  Price Trends & Vendor Comparison
# ---------------------------------------------------------------------------

def get_price_trends(db: Session, restaurant_id: str) -> list[dict]:
    rid  = _to_uuid(restaurant_id)
    now  = _now()

    ingredients = db.execute(
        select(Ingredient).where(Ingredient.restaurant_id == rid)
    ).scalars().all()

    rows = []
    for ing in ingredients:
        iid = ing.id

        def _avg_cost(days_ago_start: int, days_ago_end: int) -> Optional[float]:
            t_start = now - timedelta(days=days_ago_start)
            t_end   = now - timedelta(days=days_ago_end)
            val = db.execute(
                select(func.avg(InvoiceLineItem.unit_cost))
                .join(VendorInvoice, InvoiceLineItem.invoice_id == VendorInvoice.id)
                .where(
                    VendorInvoice.restaurant_id == rid,
                    InvoiceLineItem.ingredient_id == iid,
                    VendorInvoice.received_at >= t_start,
                    VendorInvoice.received_at < t_end,
                )
            ).scalar()
            return float(val) if val is not None else None

        # Current: avg of last 3 purchases
        last3 = db.execute(
            select(InvoiceLineItem.unit_cost)
            .join(VendorInvoice, InvoiceLineItem.invoice_id == VendorInvoice.id)
            .where(
                VendorInvoice.restaurant_id == rid,
                InvoiceLineItem.ingredient_id == iid,
            )
            .order_by(VendorInvoice.received_at.desc())
            .limit(3)
        ).scalars().all()

        if not last3:
            continue

        current_avg = float(sum(last3) / len(last3))

        def _pct_change(baseline: Optional[float]) -> Optional[float]:
            if baseline is None or baseline == 0:
                return None
            return round((current_avg - baseline) / baseline * 100, 2)

        avg30 = _avg_cost(30, 0)
        avg60 = _avg_cost(60, 30)
        avg90 = _avg_cost(90, 60)

        chg30 = _pct_change(avg30)
        chg60 = _pct_change(avg60)
        chg90 = _pct_change(avg90)

        flag = chg60 is not None and chg60 > 10.0

        action = None
        top_items: list[str] = []
        if flag:
            # Find top-3 menu items by margin impact (recipe usage × unit_cost)
            recipe_lines = db.execute(
                select(RecipeLine)
                .where(RecipeLine.ingredient_id == iid)
            ).scalars().all()
            # Enrich with units_sold (28d)
            since28 = now - timedelta(days=28)
            impacts = []
            for rl in recipe_lines:
                item = db.get(MenuItem, rl.menu_item_id)
                if not item or item.restaurant_id != rid:
                    continue
                units = db.execute(
                    select(func.sum(SalesByItem.quantity_sold))
                    .where(
                        SalesByItem.restaurant_id == rid,
                        SalesByItem.menu_item_id == rl.menu_item_id,
                        SalesByItem.business_date >= since28,
                    )
                ).scalar() or 0
                impact = float(rl.quantity) * current_avg * int(units)
                impacts.append((item.name, impact))
            impacts.sort(key=lambda x: x[1], reverse=True)
            top_items = [n for n, _ in impacts[:3]]
            action = (
                f'{ing.name} up {chg60:.1f}% in 60d — '
                f'review pricing for: {", ".join(top_items) or "no active menu items"}'
            )

        rows.append({
            'ingredient_id':      str(iid),
            'ingredient_name':    ing.name,
            'current_avg_cost':   round(current_avg, 4),
            'change_30d_pct':     chg30,
            'change_60d_pct':     chg60,
            'change_90d_pct':     chg90,
            'flag':               flag,
            'top_affected_items': top_items,
            'recommended_action': action,
        })

    return rows


def get_vendor_comparison(db: Session, restaurant_id: str, ingredient_id: str) -> list[dict]:
    rid  = _to_uuid(restaurant_id)
    iid  = _to_uuid(ingredient_id)
    now  = _now()
    since90 = now - timedelta(days=90)

    ing = db.get(Ingredient, iid)
    if not ing or ing.restaurant_id != rid:
        return []

    from app.models.inventory import Vendor

    # Aggregate per vendor: avg price and purchase count (unchanged)
    agg_rows = db.execute(
        select(
            VendorInvoice.vendor_id,
            func.avg(InvoiceLineItem.unit_cost).label('avg_price'),
            func.count(InvoiceLineItem.id).label('cnt'),
        )
        .join(VendorInvoice, InvoiceLineItem.invoice_id == VendorInvoice.id)
        .where(
            VendorInvoice.restaurant_id == rid,
            InvoiceLineItem.ingredient_id == iid,
            VendorInvoice.received_at >= since90,
        )
        .group_by(VendorInvoice.vendor_id)
    ).all()

    rows = []
    for ar in agg_rows:
        # Most recent price: unit_cost from the line with the latest received_at for this vendor
        last_price = db.execute(
            select(InvoiceLineItem.unit_cost)
            .join(VendorInvoice, InvoiceLineItem.invoice_id == VendorInvoice.id)
            .where(
                VendorInvoice.restaurant_id == rid,
                VendorInvoice.vendor_id == ar.vendor_id,
                InvoiceLineItem.ingredient_id == iid,
                VendorInvoice.received_at >= since90,
            )
            .order_by(VendorInvoice.received_at.desc())
            .limit(1)
        ).scalar()

        vendor = db.get(Vendor, ar.vendor_id)
        rows.append({
            'vendor_id':      str(ar.vendor_id),
            'vendor_name':    vendor.name if vendor else str(ar.vendor_id),
            'last_price':     round(float(last_price), 4) if last_price is not None else 0.0,
            'avg_price_90d':  round(float(ar.avg_price), 4),
            'purchase_count': int(ar.cnt),
        })
    return rows


# ---------------------------------------------------------------------------
# 11.6  Par-Level Optimization
# ---------------------------------------------------------------------------

def get_par_recommendations(db: Session, restaurant_id: str) -> list[dict]:
    rid  = _to_uuid(restaurant_id)
    settings = get_or_create_settings(db, restaurant_id)
    now  = _now()
    since28 = now - timedelta(days=28)

    ingredients = db.execute(
        select(Ingredient).where(Ingredient.restaurant_id == rid)
    ).scalars().all()

    rows = []
    for ing in ingredients:
        iid = ing.id

        total_depleted = db.execute(
            select(func.coalesce(func.sum(DepletionEvent.quantity), 0))
            .where(
                DepletionEvent.restaurant_id == rid,
                DepletionEvent.ingredient_id == iid,
                DepletionEvent.depleted_at >= since28,
            )
        ).scalar() or Decimal('0')

        daily_velocity = float(total_depleted) / 28.0

        if daily_velocity == 0:
            rows.append({
                'ingredient_id':      str(iid),
                'ingredient_name':    ing.name,
                'unit':               ing.unit,
                'current_par':        float(ing.par_level) if ing.par_level else None,
                'daily_velocity':     0.0,
                'cover_days':         None,
                'suggested_par':      None,
                'data_gap':           True,
                'recommended_action': 'no depletion data in 28d — verify this ingredient is in use',
            })
            continue

        par = float(ing.par_level) if ing.par_level else None
        cover_days = (par / daily_velocity) if par and daily_velocity > 0 else None
        suggested_par = round(daily_velocity * 7, 3)

        action = None
        if cover_days is not None:
            min_cd = int(settings.par_min_cover_days)
            max_cd = int(settings.par_max_cover_days)
            if cover_days < min_cd:
                action = (
                    f'par too low — {cover_days:.1f}d cover at current velocity; '
                    f'suggest par = {suggested_par} {ing.unit} ({min_cd}–{max_cd}d target)'
                )
            elif cover_days > max_cd:
                action = (
                    f'par too high — {cover_days:.1f}d cover risks spoilage/cash tie-up; '
                    f'suggest par = {suggested_par} {ing.unit} ({min_cd}–{max_cd}d target)'
                )
        else:
            action = f'no par level set — suggest par = {suggested_par} {ing.unit}'

        rows.append({
            'ingredient_id':      str(iid),
            'ingredient_name':    ing.name,
            'unit':               ing.unit,
            'current_par':        par,
            'daily_velocity':     round(daily_velocity, 4),
            'cover_days':         round(cover_days, 2) if cover_days else None,
            'suggested_par':      suggested_par,
            'data_gap':           False,
            'recommended_action': action,
        })

    return rows


# ---------------------------------------------------------------------------
# 11.7  Daypart / Day-of-Week Patterns
# ---------------------------------------------------------------------------

_DAYPART_LABELS = [
    ('breakfast',  0, 11),
    ('lunch',     11, 15),
    ('afternoon', 15, 17),
    ('dinner',    17, 22),
    ('late',      22, 24),
]
_DOW_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def _get_tz(tz_str: str | None) -> _zoneinfo.ZoneInfo:
    if not tz_str:
        return _zoneinfo.ZoneInfo('UTC')
    try:
        return _zoneinfo.ZoneInfo(tz_str)
    except Exception:
        return _zoneinfo.ZoneInfo('UTC')


def _localize(dt: datetime, tz: _zoneinfo.ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)


def get_sales_patterns(db: Session, restaurant_id: str, window_days: int = 28) -> dict:
    rid   = _to_uuid(restaurant_id)
    since = _now() - timedelta(days=window_days)

    restaurant = db.get(Restaurant, rid)
    tz = _get_tz(restaurant.timezone if restaurant else None)

    all_rows = db.execute(
        select(SalesByItem)
        .where(
            SalesByItem.restaurant_id == rid,
            SalesByItem.business_date >= since,
            SalesByItem.menu_item_id.is_not(None),
        )
    ).scalars().all()

    if not all_rows:
        return {'dow': [], 'daypart': [], 'coverage_pct': 0.0}

    # DOW aggregation — convert to restaurant-local time so a 23:30 UTC sale on
    # Friday doesn't land in Saturday's bucket for an EST restaurant.
    dow_rev   = [0.0] * 7
    dow_units = [0]   * 7
    for row in all_rows:
        wd = _localize(row.business_date, tz).weekday()   # Mon=0
        dow_rev[wd]   += float(row.gross_revenue or 0)
        dow_units[wd] += int(row.quantity_sold or 0)

    mean_rev = sum(dow_rev) / 7 if any(dow_rev) else 1.0
    dow_out = [
        {
            'weekday':      i,
            'weekday_name': _DOW_NAMES[i],
            'revenue':      round(dow_rev[i], 2),
            'units':        dow_units[i],
            'index':        round(dow_rev[i] / mean_rev, 2) if mean_rev else 0.0,
        }
        for i in range(7)
    ]

    # Daypart: Toast-sourced rows have real timestamps; manual and CSV are date-only.
    # CSV-imported sales use source='csv' and are date-only like manual — must not count as timestamped.
    timestamped  = [r for r in all_rows if r.source == 'toast']
    coverage_pct = round(len(timestamped) / len(all_rows), 4) if all_rows else 0.0

    dp_rev   = {label: 0.0 for label, *_ in _DAYPART_LABELS}
    dp_units = {label: 0   for label, *_ in _DAYPART_LABELS}
    for row in timestamped:
        h = _localize(row.business_date, tz).hour
        for label, start, end in _DAYPART_LABELS:
            if start <= h < end:
                dp_rev[label]   += float(row.gross_revenue or 0)
                dp_units[label] += int(row.quantity_sold or 0)
                break

    daypart_out = [
        {'daypart': label, 'revenue': round(dp_rev[label], 2), 'units': dp_units[label]}
        for label, *_ in _DAYPART_LABELS
    ]

    # Weather join — outer join against weather_days over the same window
    weather_rows = db.execute(
        select(WeatherDay)
        .where(
            WeatherDay.restaurant_id == rid,
            WeatherDay.business_date >= since.date(),
        )
        .order_by(WeatherDay.business_date)
    ).scalars().all()
    weather_out = [
        {
            'business_date': str(w.business_date),
            'precip_mm':     float(w.precip_mm) if w.precip_mm is not None else None,
            'tmax':          float(w.tmax)       if w.tmax      is not None else None,
            'tmin':          float(w.tmin)       if w.tmin      is not None else None,
        }
        for w in weather_rows
    ]

    return {'dow': dow_out, 'daypart': daypart_out, 'coverage_pct': coverage_pct, 'weather': weather_out}


# ---------------------------------------------------------------------------
# 11.8  Cost Sensitivity
# ---------------------------------------------------------------------------

def get_cost_sensitivity(db: Session, restaurant_id: str, shock_pct: float = 10.0) -> list[dict]:
    rid   = _to_uuid(restaurant_id)
    since = _now() - timedelta(days=28)

    ingredients = db.execute(
        select(Ingredient).where(Ingredient.restaurant_id == rid)
    ).scalars().all()

    rows = []
    for ing in ingredients:
        if not ing.current_cost_per_unit:
            continue
        iid = ing.id

        # All recipe lines using this ingredient
        recipe_lines = db.execute(
            select(RecipeLine).where(RecipeLine.ingredient_id == iid)
        ).scalars().all()

        exposure = 0.0
        for rl in recipe_lines:
            item = db.get(MenuItem, rl.menu_item_id)
            if not item or item.restaurant_id != rid:
                continue
            units_sold = db.execute(
                select(func.sum(SalesByItem.quantity_sold))
                .where(
                    SalesByItem.restaurant_id == rid,
                    SalesByItem.menu_item_id == rl.menu_item_id,
                    SalesByItem.business_date >= since,
                )
            ).scalar() or 0
            exposure += (
                float(rl.quantity)
                * float(ing.current_cost_per_unit)
                * (shock_pct / 100.0)
                * int(units_sold)
            )

        if exposure == 0.0:
            continue

        rows.append({
            'ingredient_id':      str(iid),
            'ingredient_name':    ing.name,
            'exposure_dollars':   round(exposure, 2),
            'recommended_action': (
                f'most exposed to {ing.name} — a {shock_pct:.0f}% price rise costs '
                f'${exposure:.2f} over 28d; consider a hedge item or portion review'
            ),
        })

    rows.sort(key=lambda r: r['exposure_dollars'], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# 11.9  Break-Even
# ---------------------------------------------------------------------------

def get_break_even(db: Session, restaurant_id: str) -> dict:
    rid  = _to_uuid(restaurant_id)
    settings = get_or_create_settings(db, restaurant_id)

    if not settings.monthly_fixed_costs:
        return {
            'daily_breakeven':   None,
            'avg_daily_revenue': None,
            'daily_surplus':     None,
            'data_gap':          'enter monthly fixed costs in Settings to enable break-even',
        }

    now   = _now()
    since = now - timedelta(days=30)
    fc_summary = get_food_cost_summary(db, str(rid), since, now)

    blended_fc_pct = fc_summary.get('food_cost_pct')
    if blended_fc_pct is None:
        return {
            'daily_breakeven':   None,
            'avg_daily_revenue': None,
            'daily_surplus':     None,
            'data_gap':          'no sales data in the last 30 days to compute blended margin',
        }

    gross_margin_pct = 1.0 - (blended_fc_pct / 100.0)
    if gross_margin_pct <= 0:
        return {
            'daily_breakeven':   None,
            'avg_daily_revenue': None,
            'daily_surplus':     None,
            'data_gap':          'blended gross margin is zero or negative — food cost exceeds revenue',
        }

    daily_fixed     = float(settings.monthly_fixed_costs) / 30.4
    daily_breakeven = daily_fixed / gross_margin_pct

    avg_daily_revenue = fc_summary['total_revenue'] / 30.0
    daily_surplus     = avg_daily_revenue - daily_breakeven

    return {
        'daily_breakeven':   round(daily_breakeven, 2),
        'avg_daily_revenue': round(avg_daily_revenue, 2),
        'daily_surplus':     round(daily_surplus, 2),
        'data_gap':          None,
    }


# ---------------------------------------------------------------------------
# 12.1  Covers / Revenue-per-Seat
# ---------------------------------------------------------------------------

def get_covers_insight(db: Session, restaurant_id: str, window_days: int = 28) -> dict:
    rid      = _to_uuid(restaurant_id)
    settings = get_or_create_settings(db, restaurant_id)
    since    = _now() - timedelta(days=window_days)

    total_rev = float(db.execute(
        select(func.coalesce(func.sum(SalesByItem.gross_revenue), 0))
        .where(SalesByItem.restaurant_id == rid, SalesByItem.business_date >= since)
    ).scalar() or 0)

    total_covers = int(db.execute(
        select(func.coalesce(func.sum(SalesSummary.covers), 0))
        .where(SalesSummary.restaurant_id == rid, SalesSummary.business_date >= since)
    ).scalar() or 0)

    seat_count = settings.seat_count
    avg_check  = round(total_rev / total_covers, 2) if total_covers > 0 else None
    rev_per_seat_per_day = (
        round(total_rev / (seat_count * window_days), 2)
        if seat_count and seat_count > 0 else None
    )

    return {
        'avg_check':               avg_check,
        'revenue_per_seat_per_day': rev_per_seat_per_day,
        'seat_count':              seat_count,
        'data_gap': (
            'set seat_count in Settings to enable revenue-per-seat-per-day'
            if not seat_count else None
        ),
    }


# ---------------------------------------------------------------------------
# 12.2  Adjustment Report
# ---------------------------------------------------------------------------

def get_adjustment_report(db: Session, restaurant_id: str, window_days: int = 28) -> list[dict]:
    rid   = _to_uuid(restaurant_id)
    since = _now() - timedelta(days=window_days)

    agg_rows = db.execute(
        select(
            SaleAdjustment.adjustment_type,
            func.coalesce(func.sum(SaleAdjustment.amount), 0).label('total'),
            func.count(SaleAdjustment.id).label('cnt'),
        )
        .where(SaleAdjustment.restaurant_id == rid, SaleAdjustment.business_date >= since)
        .group_by(SaleAdjustment.adjustment_type)
    ).all()

    total_rev = float(db.execute(
        select(func.coalesce(func.sum(SalesByItem.gross_revenue), 0))
        .where(SalesByItem.restaurant_id == rid, SalesByItem.business_date >= since)
    ).scalar() or 0)

    rows = []
    for ar in agg_rows:
        total_adj  = float(ar.total or 0)
        cnt        = int(ar.cnt or 0)
        pct_rev    = round(total_adj / total_rev * 100, 2) if total_rev > 0 else None
        flag_high  = pct_rev is not None and pct_rev > 3.0
        action     = None
        if flag_high:
            action = (
                f'{ar.adjustment_type} total ${total_adj:.2f} ({pct_rev:.1f}% of revenue, '
                f'{cnt} occurrences over {window_days}d) — investigate by employee and daypart'
            )
        rows.append({
            'adjustment_type':    ar.adjustment_type,
            'total_amount':       round(total_adj, 2),
            'count':              cnt,
            'pct_of_revenue':     pct_rev,
            'flag_high':          flag_high,
            'recommended_action': action,
        })

    rows.sort(key=lambda r: r['total_amount'], reverse=True)
    return rows
