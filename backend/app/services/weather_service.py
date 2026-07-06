"""Fetch daily weather from Open-Meteo and upsert into weather_days.

Called only from the nightly Celery task (fetch_nightly_weather).
Verification scripts insert weather_days rows directly — never call this in tests.
"""
import logging
from datetime import date
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.weather import WeatherDay
import uuid as _uuid

logger = logging.getLogger(__name__)

_OPEN_METEO_URL = 'https://archive-api.open-meteo.com/v1/archive'


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


def fetch_weather_for_restaurant(db: Session, restaurant, fetch_date: date) -> WeatherDay | None:
    """Fetch weather for the restaurant's lat/lon on fetch_date and upsert into weather_days.

    Restaurant ORM object must have `.id`; settings must have lat/lon.
    Returns None if no lat/lon configured or if Open-Meteo request fails.
    """
    from app.services.insights_service import get_or_create_settings

    settings = get_or_create_settings(db, str(restaurant.id))
    if not settings.lat or not settings.lon:
        logger.debug('Restaurant %s: no lat/lon — skipping weather fetch', restaurant.id)
        return None

    params = {
        'latitude':  float(settings.lat),
        'longitude': float(settings.lon),
        'start_date': str(fetch_date),
        'end_date':   str(fetch_date),
        'daily':      'precipitation_sum,temperature_2m_max,temperature_2m_min',
        'timezone':   'UTC',
    }

    try:
        resp = httpx.get(_OPEN_METEO_URL, params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error('Open-Meteo request failed for restaurant %s: %s', restaurant.id, exc)
        return None

    daily   = data.get('daily', {})
    precip  = (daily.get('precipitation_sum') or [None])[0]
    tmax    = (daily.get('temperature_2m_max') or [None])[0]
    tmin    = (daily.get('temperature_2m_min') or [None])[0]

    rid      = _to_uuid(restaurant.id)
    existing = db.execute(
        select(WeatherDay).where(
            WeatherDay.restaurant_id == rid,
            WeatherDay.business_date == fetch_date,
        )
    ).scalar_one_or_none()

    def _d(v):
        return Decimal(str(v)) if v is not None else None

    if existing:
        existing.precip_mm = _d(precip)
        existing.tmax      = _d(tmax)
        existing.tmin      = _d(tmin)
        db.commit()
        db.refresh(existing)
        return existing

    row = WeatherDay(
        restaurant_id = rid,
        business_date = fetch_date,
        precip_mm     = _d(precip),
        tmax          = _d(tmax),
        tmin          = _d(tmin),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
