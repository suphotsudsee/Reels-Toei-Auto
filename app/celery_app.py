from celery import Celery
from celery.schedules import crontab
from .config import settings

celery = Celery("reels_factory", broker=settings.redis_url, backend=settings.redis_url, include=["app.tasks"])
celery.conf.update(
    timezone=settings.tz,
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "produce-three-times-weekly": {
            "task": "app.tasks.create_scheduled_job",
            "schedule": crontab(hour=9, minute=0, day_of_week="mon,wed,fri"),
        }
    },
)

