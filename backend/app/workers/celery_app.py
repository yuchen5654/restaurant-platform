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
    'fetch-nightly-weather': {
        'task':     'app.workers.tasks.fetch_nightly_weather',
        'schedule': crontab(hour=4, minute=0),
    },
    'compute-benchmarks': {
        'task':     'app.workers.tasks.compute_benchmarks',
        'schedule': crontab(hour=4, minute=30),
    },
}
