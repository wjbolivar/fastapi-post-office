from __future__ import annotations

import importlib
import sys
from datetime import datetime, timedelta, timezone

from fastapi_post_office.config import settings
from fastapi_post_office.db import (
    Base,
    EmailRepository,
    create_engine_from_url,
    create_session_factory,
)
from fastapi_post_office.db.models import EmailMessage, EmailStatus


def _install_fake_celery():
    class FakeCelery:
        def __init__(self, *args, **kwargs):
            self.conf = type("Conf", (), {})()

        def task(self, *args, **kwargs):
            def decorator(fn):
                fn.delay = lambda *a, **k: fn(*a, **k)
                return fn

            return decorator

    fake_module = type("celery", (), {"Celery": FakeCelery})
    sys.modules["celery"] = fake_module


def test_send_and_retry_tasks(tmp_path):
    _install_fake_celery()
    settings.celery_broker_url = "memory://"
    db_url = f"sqlite+pysqlite:///{tmp_path / 'tasks.db'}"
    settings.database_url = db_url

    engine = create_engine_from_url(db_url)
    Base.metadata.create_all(engine)
    session = create_session_factory(engine)()
    repo = EmailRepository(session)

    message = EmailMessage(
        from_email="no-reply@example.com",
        to_json=["user@example.com"],
        cc_json=[],
        bcc_json=[],
        subject="Hello",
        html_body=None,
        text_body="Hi",
        attempt_count=0,
        max_attempts=3,
        status=EmailStatus.QUEUED,
        next_attempt_at=datetime.now(timezone.utc),
    )
    retry_message = EmailMessage(
        from_email="no-reply@example.com",
        to_json=["user@example.com"],
        cc_json=[],
        bcc_json=[],
        subject="Hello",
        html_body=None,
        text_body="Hi",
        attempt_count=0,
        max_attempts=3,
        status=EmailStatus.RETRYING,
        next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    repo.create_message(message)
    repo.create_message(retry_message)
    repo.commit()
    message_id = str(message.id)
    session.close()
    engine.dispose()

    send_module = importlib.import_module("fastapi_post_office.tasks.send")
    periodic_module = importlib.import_module("fastapi_post_office.tasks.periodic")

    importlib.reload(send_module)
    importlib.reload(periodic_module)

    # direct send
    send_module.send_message(message_id)

    # retry queue
    count = periodic_module.retry_due_messages()
    assert count >= 1

    # cleanup
    settings.retention_days = 0
    deleted = periodic_module.cleanup_sent_messages()
    assert deleted >= 0
