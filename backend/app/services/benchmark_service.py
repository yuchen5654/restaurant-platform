"""
Peer benchmarking: cross-restaurant percentile aggregation.
Hard rule: n < 5 -> row is never written or exposed.
BenchmarkStats has no restaurant_id — it is deliberately cross-tenant aggregate data.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.benchmarks import BenchmarkStats
from app.models.restaurant import Restaurant

logger = logging.getLogger(__name__)

MIN_COHORT = 5   # hard rule: never write or expose a benchmark from fewer than 5 restaurants

_METRICS = [
    'food_cost_pct',
    'prime_cost_pct',
    'labor_pct',
    'avg_check',
]


def _percentile(values: list[float], p: float) -> float:
    """Simple percentile via linear interpolation."""
    if not values:
        raise ValueError('empty list')
    s    = sorted(values)
    n    = len(s)
    idx  = (n - 1) * p / 100.0
    lo   = int(idx)
    hi   = lo + 1
    frac = idx - lo
    if hi >= n:
        return s[lo]
    return s[lo] + frac * (s[hi] - s[lo])


def _get_restaurant_metrics(db: Session, restaurant_id: str) -> dict:
    """Compute the standard 28d metrics for one restaurant. Returns dict[metric -> float|None]."""
    from app.services.labor_service  import get_prime_cost
    from app.services.insights_service import get_covers_insight

    prime  = get_prime_cost(db, restaurant_id, window_days=28)
    covers = get_covers_insight(db, restaurant_id, window_days=28)

    return {
        'food_cost_pct':  prime.get('food_cost_pct'),
        'prime_cost_pct': prime.get('prime_cost_pct'),
        'labor_pct':      prime.get('labor_pct'),
        'avg_check':      covers.get('avg_check'),
    }


def run_benchmark_computation(db: Session) -> None:
    """Compute and persist benchmark percentiles for all metrics × cohorts.
    Called from the nightly Celery task. n < MIN_COHORT → row not written.
    """
    from app.services.insights_service import get_or_create_settings

    today = datetime.now(timezone.utc).date()

    restaurants = db.execute(
        select(Restaurant).where(Restaurant.is_active.is_(True))
    ).scalars().all()

    # Collect metrics per restaurant, grouped by restaurant_type
    by_cohort: dict[str, list[dict]] = {'all': []}

    for r in restaurants:
        rid  = str(r.id)
        sett = get_or_create_settings(db, rid)
        try:
            metrics = _get_restaurant_metrics(db, rid)
        except Exception:
            logger.exception('benchmark: metric compute failed for restaurant %s', rid)
            continue

        by_cohort['all'].append(metrics)

        r_type = sett.restaurant_type
        if r_type:
            by_cohort.setdefault(r_type, []).append(metrics)

    # Write percentile rows
    for cohort, metric_dicts in by_cohort.items():
        n = len(metric_dicts)
        if n < MIN_COHORT:
            logger.info('benchmark: cohort=%s n=%d < %d — skipping', cohort, n, MIN_COHORT)
            continue

        for metric in _METRICS:
            values = [m[metric] for m in metric_dicts if m.get(metric) is not None]
            if len(values) < MIN_COHORT:
                logger.info(
                    'benchmark: cohort=%s metric=%s valid_n=%d < %d — skipping',
                    cohort, metric, len(values), MIN_COHORT,
                )
                continue

            p25 = _percentile(values, 25)
            p50 = _percentile(values, 50)
            p75 = _percentile(values, 75)

            # Upsert: delete existing row for same (metric, cohort, stat_date) then insert
            existing = db.execute(
                select(BenchmarkStats).where(
                    BenchmarkStats.metric    == metric,
                    BenchmarkStats.cohort    == cohort,
                    BenchmarkStats.stat_date == today,
                )
            ).scalar_one_or_none()

            if existing:
                existing.p25 = Decimal(str(round(p25, 4)))
                existing.p50 = Decimal(str(round(p50, 4)))
                existing.p75 = Decimal(str(round(p75, 4)))
                existing.n   = len(values)
            else:
                row = BenchmarkStats(
                    metric    = metric,
                    cohort    = cohort,
                    stat_date = today,
                    p25       = Decimal(str(round(p25, 4))),
                    p50       = Decimal(str(round(p50, 4))),
                    p75       = Decimal(str(round(p75, 4))),
                    n         = len(values),
                )
                db.add(row)

            logger.info('benchmark: cohort=%s metric=%s n=%d p50=%.2f', cohort, metric, len(values), p50)

    db.commit()


def get_benchmarks(db: Session, restaurant_id: str) -> dict:
    """Return own 28d values vs cohort percentiles.
    Falls back to 'all' cohort if the restaurant_type cohort has no row.
    """
    from app.services.insights_service import get_or_create_settings

    sett = get_or_create_settings(db, restaurant_id)
    own  = _get_restaurant_metrics(db, restaurant_id)

    # Most recent stat_date for any benchmark row
    latest = db.execute(
        select(BenchmarkStats.stat_date)
        .order_by(BenchmarkStats.stat_date.desc())
        .limit(1)
    ).scalar_one_or_none()

    if not latest:
        return {
            'own': own,
            'benchmarks': [],
            'cohort': None,
            'stat_date': None,
            'caveat': 'no peer data yet — benchmarks populate once enough restaurants join',
        }

    r_type   = sett.restaurant_type
    cohort   = r_type if r_type else 'all'

    rows = []
    for metric in _METRICS:
        # Try specific cohort, fall back to 'all'
        stat = db.execute(
            select(BenchmarkStats).where(
                BenchmarkStats.metric    == metric,
                BenchmarkStats.cohort    == cohort,
                BenchmarkStats.stat_date == latest,
            )
        ).scalar_one_or_none()

        if stat is None and cohort != 'all':
            stat = db.execute(
                select(BenchmarkStats).where(
                    BenchmarkStats.metric    == metric,
                    BenchmarkStats.cohort    == 'all',
                    BenchmarkStats.stat_date == latest,
                )
            ).scalar_one_or_none()

        if stat is None:
            rows.append({
                'metric':     metric,
                'own_value':  own.get(metric),
                'p25':        None,
                'p50':        None,
                'p75':        None,
                'n':          None,
                'cohort_used': None,
            })
        else:
            rows.append({
                'metric':      metric,
                'own_value':   own.get(metric),
                'p25':         float(stat.p25),
                'p50':         float(stat.p50),
                'p75':         float(stat.p75),
                'n':           stat.n,
                'cohort_used': stat.cohort,
            })

    used_cohort = rows[0]['cohort_used'] if rows else None
    caveat = (
        f'benchmarked against {used_cohort!r} cohort ({rows[0]["n"]} restaurants)'
        if (rows and rows[0]['n']) else 'no peer data for this metric yet'
    )

    return {
        'own':        own,
        'benchmarks': rows,
        'cohort':     cohort,
        'stat_date':  str(latest),
        'caveat':     caveat,
    }
