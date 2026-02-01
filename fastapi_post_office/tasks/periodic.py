from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

from fastapi_post_office.config import settings
from fastapi_post_office.db import EmailRepository, create_engine_from_url, create_session_factory
from fastapi_post_office.tasks.celery_app import get_celery_app
from fastapi_post_office.tasks.send import send_message


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


@celery_app.task(name="fastapi_post_office.retry_due")
def retry_due_messages() -> int:
    count = 0
    with _session_scope() as session:
        repo = EmailRepository(session)
        due = repo.list_due_messages(now=datetime.now(timezone.utc))
        for message in due:
            send_message.delay(str(message.id))
            count += 1
    return count


@celery_app.task(name="fastapi_post_office.cleanup_sent")
def cleanup_sent_messages() -> int:
    with _session_scope() as session:
        repo = EmailRepository(session)
        deleted = repo.cleanup_sent(settings.retention_days)
    return deleted
