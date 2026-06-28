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
def run_nightly_alerts():
    """Placeholder — implemented in Step 6."""
    pass
