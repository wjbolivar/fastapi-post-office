from __future__ import annotations

from typing import Optional

from fastapi_post_office.config import settings


def get_celery_app() -> "Celery":
    try:
        from celery import Celery
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Celery is not installed. Install with fastapi-post-office[celery].") from exc

    broker = settings.celery_broker_url
    backend = settings.celery_backend_url
    if not broker:
        raise RuntimeError("FAPO_CELERY_BROKER_URL is required for Celery usage")

    app = Celery("fastapi_post_office", broker=broker, backend=backend)
    app.conf.task_always_eager = False
    app.conf.task_ignore_result = True
    return app
