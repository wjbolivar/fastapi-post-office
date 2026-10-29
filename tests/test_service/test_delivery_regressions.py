from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from fastapi_post_office.backends.base import SendResult
from fastapi_post_office.db.models import Base, EmailMessage, EmailStatus, SuppressionReason
from fastapi_post_office.db.repository import EmailRepository
from fastapi_post_office.service import EmailService


def enqueue(service, key="key"):
    return service.enqueue(
        to=["user@example.com"], subject="Hello", html=None, text="Hi", idempotency_key=key
    )


def test_duplicate_workers_send_only_once(repo, db_url):
    message_id = enqueue(EmailService(repo)).id
    entered, release = Event(), Event()
    calls = []

    class BlockingBackend:
        name = "console"

        def send(self, message):
            calls.append(message.id)
            entered.set()
            assert release.wait(5)
            return SendResult(ok=True)

    def worker():
        engine = create_engine(db_url)
        try:
            with Session(engine) as session:
                service = EmailService(EmailRepository(session))
                service.backend = BlockingBackend()
                return service.send_now(message_id).status
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker)
        try:
            assert entered.wait(5)
            assert pool.submit(worker).result(timeout=5) == EmailStatus.SENDING
        finally:
            release.set()
        assert first.result(timeout=5) == EmailStatus.SENT
    assert calls == [message_id]


def test_retry_schedule_and_exhaustion(repo):
    service = EmailService(repo)
    message = enqueue(service)
    message.max_attempts = 2
    repo.commit()

    class BrokenBackend:
        name = "console"

        def send(self, message):
            return SendResult(ok=False, error_message="Temporary failure", error_code="temporary")

    service.backend = BrokenBackend()
    assert service.send_now(message.id).status == EmailStatus.RETRYING
    assert message.attempt_count == 1
    assert "secret" not in message.last_error_message
    service.send_now(message.id)
    assert message.attempt_count == 1  # duplicate task cannot bypass retry delay
    message.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    repo.commit()
    assert service.send_now(message.id).status == EmailStatus.FAILED
    assert message.attempt_count == 2
    service.send_now(message.id)
    assert message.attempt_count == 2


def test_suppressed_after_enqueue_is_not_sent(repo):
    service = EmailService(repo)
    message = enqueue(service)
    repo.add_suppression("user@example.com", SuppressionReason.COMPLAINT)
    repo.commit()
    assert service.send_now(message.id).status == EmailStatus.FAILED
    assert message.last_error_message == "Recipient suppressed"


def test_normalized_idempotency_and_unique_conflict(repo):
    service = EmailService(repo)
    original = enqueue(service, " key ")
    assert enqueue(service, "key").id == original.id
    duplicate = EmailMessage(
        from_email=original.from_email,
        to_json=original.to_json,
        cc_json=[],
        bcc_json=[],
        subject="Different",
        text_body="Body",
        idempotency_key="key",
    )
    assert repo.create_message(duplicate).id == original.id
    repo.commit()
    assert repo.get_message(original.id).subject == "Hello"


def test_due_queue_is_bounded_and_excludes_future(repo):
    service = EmailService(repo)
    for i in range(4):
        enqueue(service, str(i))
    future = enqueue(service, "future")
    future.next_attempt_at = datetime.now(timezone.utc) + timedelta(days=1)
    repo.commit()
    due = repo.list_due_messages(limit=2)
    assert len(due) == 2
    assert future.id not in [m.id for m in due]
    with pytest.raises(ValueError):
        repo.list_due_messages(limit=0)


@pytest.mark.parametrize("dialect", [mysql.dialect(), postgresql.dialect(), sqlite.dialect()])
def test_schema_compiles_for_supported_databases(dialect):
    for table in Base.metadata.sorted_tables:
        assert str(CreateTable(table).compile(dialect=dialect))


def test_delivery_uses_saved_provider(repo, monkeypatch):
    service = EmailService(repo)
    msg = enqueue(service)
    msg.provider = "original"
    repo.commit()
    calls = []

    class OriginalBackend:
        name = "original"

        def send(self, message):
            calls.append(message.id)
            return SendResult(ok=True)

    def lookup(name, *, config):
        assert name == "original"
        return OriginalBackend()

    monkeypatch.setattr("fastapi_post_office.service.email_service.get_backend", lookup)
    assert service.send_now(msg.id).status == EmailStatus.SENT
    assert calls == [msg.id]


def test_permanent_failure_is_not_retried(repo):
    service = EmailService(repo)
    msg = enqueue(service)

    class PermanentFailure:
        name = "console"

        def send(self, message):
            return SendResult(ok=False, retryable=False, error_message="Permanent failure")

    service.backend = PermanentFailure()
    assert service.send_now(msg.id).status == EmailStatus.FAILED
    assert msg.attempt_count == 1
    assert msg.next_attempt_at is None
