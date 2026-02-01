from __future__ import annotations

from contextlib import contextmanager

import uuid

from fastapi_post_office.config import settings
from fastapi_post_office.db import EmailRepository, create_engine_from_url, create_session_factory
from fastapi_post_office.service import EmailService
from fastapi_post_office.tasks.celery_app import get_celery_app


@contextmanager
def _session_scope():
    engine = create_engine_from_url(settings.database_url)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


celery_app = get_celery_app()


@celery_app.task(name="fastapi_post_office.send_message")
def send_message(message_id: str) -> None:
    try:
        parsed_id = uuid.UUID(str(message_id))
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid message_id") from exc
    with _session_scope() as session:
        repo = EmailRepository(session)
        service = EmailService(repo)
        service.send_now(parsed_id)
