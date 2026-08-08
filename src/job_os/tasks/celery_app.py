from celery import Celery
from celery.schedules import crontab

from job_os.config import get_settings

settings = get_settings()

celery_app = Celery(
    "job_os",
    broker=settings.celery_broker_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "daily-discovery": {
            "task": "job_os.tasks.workflows.run_daily_discovery",
            "schedule": crontab(hour=6, minute=0),
        },
        "live-job-sync": {
            "task": "job_os.tasks.workflows.run_discovery_only",
            "schedule": crontab(minute="*/30"),
        },
        "email-sync": {
            "task": "job_os.tasks.workflows.run_email_sync",
            "schedule": crontab(minute="*/15"),
        },
    },
)

celery_app.autodiscover_tasks(["job_os.tasks"])
