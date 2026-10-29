from __future__ import annotations

from datetime import datetime, timezone

from fastapi_post_office.config import settings
from fastapi_post_office.db import EmailRepository
from fastapi_post_office.tasks.celery_app import get_celery_app
from fastapi_post_office.tasks.send import send_message
from fastapi_post_office.tasks.session import session_scope as _session_scope

celery_app = get_celery_app()


@celery_app.task(name="fastapi_post_office.retry_due")
def retry_due_messages() -> int:
    count = 0
    with _session_scope() as session:
        repo = EmailRepository(session)
        due = repo.list_due_messages(
            now=datetime.now(timezone.utc), limit=settings.queue_batch_size
        )
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
