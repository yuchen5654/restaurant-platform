from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery('restaurant_platform', broker=settings.REDIS_URL)

celery_app.conf.beat_schedule = {
    'pull-toast-daily': {
        'task':     'app.workers.tasks.pull_all_toast_restaurants',
        'schedule': crontab(hour=3, minute=0),
    },
    'run-nightly-alerts': {
        'task':     'app.workers.tasks.run_nightly_alerts',
        'schedule': crontab(hour=3, minute=30),
    },
}
