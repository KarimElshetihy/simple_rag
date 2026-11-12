from celery import Celery

from src.helpers.config import get_settings


settings = get_settings()

celery_app = Celery(
    "simple_rag",
    broker=settings.celery_broker_url,
)
celery_app.conf.update(
    accept_content=["json"],
    include=["src.infrastructure.celery.tasks"],
    task_serializer="json",
    result_serializer="json",
    task_send_sent_event=True,
    worker_send_task_events=True,
    broker_connection_retry_on_startup=True,
)
