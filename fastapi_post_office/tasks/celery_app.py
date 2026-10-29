from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi_post_office.config import settings

if TYPE_CHECKING:
    from celery import Celery


def get_celery_app() -> Celery:
    try:
        from celery import Celery
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Celery is not installed. Install with fastapi-post-office[celery]."
        ) from exc

    broker = settings.celery_broker_url
    backend = settings.celery_backend_url
    if not broker:
        raise RuntimeError("FAPO_CELERY_BROKER_URL is required for Celery usage")

    return _create_app(broker, backend, Celery, settings.dispatch_interval_seconds)


@lru_cache(maxsize=8)
def _create_app(broker, backend, celery_class, dispatch_interval) -> Celery:
    app = celery_class(
        "fastapi_post_office",
        broker=broker,
        backend=backend,
        include=["fastapi_post_office.tasks.send", "fastapi_post_office.tasks.periodic"],
    )
    app.conf.task_always_eager = False
    app.conf.task_ignore_result = True
    app.conf.accept_content = ["json"]
    app.conf.task_serializer = "json"
    app.conf.result_serializer = "json"
    app.conf.worker_prefetch_multiplier = 1
    app.conf.beat_schedule = {
        "fapo-dispatch-due": {
            "task": "fastapi_post_office.retry_due",
            "schedule": dispatch_interval,
        },
        "fapo-cleanup": {"task": "fastapi_post_office.cleanup_sent", "schedule": 86400.0},
    }
    return app
