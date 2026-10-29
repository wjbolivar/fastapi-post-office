from __future__ import annotations

import uuid

from fastapi_post_office.db import EmailRepository
from fastapi_post_office.service import EmailService
from fastapi_post_office.tasks.celery_app import get_celery_app
from fastapi_post_office.tasks.session import session_scope as _session_scope

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
