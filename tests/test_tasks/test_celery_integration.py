import os
import subprocess
import sys


def test_real_celery_registration_and_eager_dispatch(tmp_path):
    code = """
from fastapi_post_office.db import Base, EmailRepository, create_engine_from_url, create_session_factory
from fastapi_post_office.config import settings
from fastapi_post_office.service import EmailService
from fastapi_post_office.db.models import EmailStatus
from fastapi_post_office.tasks.send import celery_app, send_message
from fastapi_post_office.tasks.periodic import celery_app as periodic_app, retry_due_messages
assert celery_app is periodic_app
assert celery_app.conf.accept_content == ["json"]
assert "fapo-dispatch-due" in celery_app.conf.beat_schedule
celery_app.conf.task_always_eager = True
engine = create_engine_from_url(settings.database_url)
Base.metadata.create_all(engine)
with create_session_factory(engine)() as session:
    service = EmailService(EmailRepository(session))
    message = service.enqueue(to=["a@example.com"], subject="Hi", html=None, text="Hi", idempotency_key="celery")
    message_id = message.id
    result = retry_due_messages.apply(throw=True)
    assert result.result == 1
    session.refresh(message)
    assert message.status == EmailStatus.SENT
    send_message.apply(args=[str(message_id)], throw=True)
    session.refresh(message)
    assert message.attempt_count == 1
engine.dispose()
"""
    env = dict(
        os.environ,
        FAPO_CELERY_BROKER_URL="memory://",
        FAPO_DATABASE_URL=f"sqlite+pysqlite:///{tmp_path / 'celery.db'}",
        FAPO_EMAIL_BACKEND="console",
    )
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
