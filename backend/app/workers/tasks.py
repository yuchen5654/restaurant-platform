import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.restaurant import Restaurant
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def pull_all_toast_restaurants():
    """Nightly task: pull yesterday's Toast orders for every active restaurant."""
    from app.config import settings
    from app.services.pos_ingestion_service import ingest_toast_day

    db        = SessionLocal()
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    try:
        restaurants = (
            db.query(Restaurant)
            .filter(
                Restaurant.toast_location_guid.is_not(None),
                Restaurant.is_active.is_(True),
            )
            .all()
        )
        for r in restaurants:
            try:
                result = asyncio.run(ingest_toast_day(
                    db, str(r.id), r.toast_location_guid,
                    settings.TOAST_CLIENT_ID,
                    settings.TOAST_CLIENT_SECRET,
                    yesterday,
                ))
                logger.info('Restaurant %s: %s', r.name, result)
            except Exception:
                logger.exception('Toast pull failed for restaurant %s', r.name)
    finally:
        db.close()


@celery_app.task
def fetch_nightly_weather():
    """Nightly task: pull yesterday's weather for every restaurant with lat/lon set."""
    from app.services.weather_service import fetch_weather_for_restaurant
    from app.services.insights_service import get_or_create_settings

    db        = SessionLocal()
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    try:
        restaurants = (
            db.query(Restaurant)
            .filter(Restaurant.is_active.is_(True))
            .all()
        )
        for r in restaurants:
            try:
                settings = get_or_create_settings(db, str(r.id))
                if settings.lat and settings.lon:
                    result = fetch_weather_for_restaurant(db, r, yesterday)
                    if result:
                        logger.info('Restaurant %s: weather fetched for %s', r.name, yesterday)
            except Exception:
                logger.exception('Weather fetch failed for restaurant %s', r.name)
    finally:
        db.close()


@celery_app.task
def run_nightly_alerts():
    from app.services.alert_service import run_alerts_for_restaurant

    db    = SessionLocal()
    today = datetime.now(timezone.utc)
    try:
        restaurants = (
            db.query(Restaurant)
            .filter(Restaurant.is_active.is_(True))
            .all()
        )
        for r in restaurants:
            try:
                alerts = run_alerts_for_restaurant(db, str(r.id), today)
                if alerts:
                    logger.info('Restaurant %s: %d alert(s) stored', r.name, len(alerts))
            except Exception:
                logger.exception('Alert check failed for restaurant %s', r.name)
    finally:
        db.close()
