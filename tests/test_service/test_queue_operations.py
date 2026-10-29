import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from fastapi_post_office import (
    EmailService,
    InvalidTransitionError,
    MessageNotFoundError,
    TransactionModeError,
    ValidationError,
)
from fastapi_post_office.backends.base import SendResult
from fastapi_post_office.cli.main import app
from fastapi_post_office.db import (
    AsyncEmailRepository,
    Base,
    EmailAttempt,
    EmailStatus,
)
from fastapi_post_office.queue import AsyncQueueManager, QueueManager
from fastapi_post_office.service import AsyncEmailService


def enqueue(repo):
    return EmailService(repo).enqueue(
        to=["private@example.com"],
        subject="secret",
        text="private-body",
        idempotency_key=str(uuid4()),
    )


def change(queue, message_id, action, expected_attempt=0, **kwargs):
    return queue.transition(
        message_id,
        action=action,
        expected_attempt=expected_attempt,
        actor="operator",
        note="provider logs checked",
        **kwargs,
    )


def test_cancel_and_cli_privacy(repo):
    msg = enqueue(repo)
    queue = QueueManager(repo.session)
    assert queue.metrics()["due"] == 1
    result = CliRunner().invoke(app, ["queue", "inspect", str(msg.id)])
    assert result.exit_code == 0, result.output
    assert "private" not in result.output and "secret" not in result.output
    result = CliRunner().invoke(
        app,
        [
            "queue",
            "transition",
            str(msg.id),
            "cancel",
            "--expected-attempt",
            "0",
            "--actor",
            "ops",
            "--note",
            "requested cancellation",
        ],
    )
    assert result.exit_code == 0, result.output
    assert queue.inspect(msg.id)["status"] == "CANCELLED"
    assert queue.metrics()["counts"]["CANCELLED"] == 1
    assert EmailService(repo).send_now(msg.id).attempt_count == 0
    with pytest.raises(InvalidTransitionError):
        change(queue, msg.id, "retry", acknowledge_duplicate_risk=True)


def test_attempt_history_failure_retry_success(repo):
    msg = enqueue(repo)
    service = EmailService(repo)

    class Fail:
        name = "console"

        def send(self, message):
            return SendResult(
                ok=False,
                retryable=False,
                error_code="test_failure",
                error_message="private diagnostic",
            )

    service.backend = Fail()
    service.send_now(msg.id)
    queue = QueueManager(repo.session)
    assert queue.inspect(msg.id)["attempts"][0]["outcome"] == "FAILED"
    with pytest.raises(InvalidTransitionError):
        change(queue, msg.id, "retry", expected_attempt=1)
    with pytest.raises(InvalidTransitionError):
        change(queue, msg.id, "retry", expected_attempt=0, acknowledge_duplicate_risk=True)
    change(queue, msg.id, "retry", expected_attempt=1, acknowledge_duplicate_risk=True)
    EmailService(repo).send_now(msg.id)
    data = queue.inspect(msg.id)
    assert [a["number"] for a in data["attempts"]] == [1, 2]
    assert data["attempts"][1]["outcome"] == "SENT"
    assert data["attempts"][1]["duration_ms"] >= 0
    assert data["events"][0]["action"] == "retry"
    assert queue.metrics()["attempts"] == 2


@pytest.mark.parametrize(
    "action,status",
    [("reconcile-sent", "SENT"), ("reconcile-failed", "FAILED"), ("reconcile-retry", "QUEUED")],
)
def test_reconcile_invalidates_old_worker(repo, action, status):
    msg = enqueue(repo)
    assert repo.claim_message(msg.id)
    repo.session.refresh(msg)
    queue = QueueManager(repo.session)
    with pytest.raises(InvalidTransitionError):
        change(queue, msg.id, action, expected_attempt=1)
    # Independent session acts as operator; worker still holds its old token.
    with Session(repo.session.bind) as operator:
        data = change(
            QueueManager(operator),
            msg.id,
            action,
            expected_attempt=1,
            acknowledge_duplicate_risk=True,
        )
        assert data["status"] == status
    with pytest.raises(InvalidTransitionError):
        repo.finish_attempt(msg, SendResult(ok=True), datetime.now(timezone.utc), 1)
    assert queue.inspect(msg.id)["status"] == status


def test_ambiguous_delivery_is_not_automatically_retried(repo):
    msg = enqueue(repo)

    class Ambiguous:
        name = "console"

        def send(self, message):
            return SendResult(ok=False, ambiguous=True, error_code="transport_unknown")

    service = EmailService(repo, backend=Ambiguous())
    assert service.send_now(msg.id).status == EmailStatus.SENDING
    service.send_now(msg.id)
    assert msg.attempt_count == 1
    assert QueueManager(repo.session).inspect(msg.id)["attempts"][0]["outcome"] == "UNKNOWN"


def test_cleanup_history_dry_run_and_stuck_metrics(repo):
    msg = enqueue(repo)
    EmailService(repo).send_now(msg.id)
    msg.completed_at = datetime.now(timezone.utc) - timedelta(days=60)
    repo.commit()
    pending = enqueue(repo)
    repo.claim_message(pending.id)
    repo.session.refresh(pending)
    pending.sending_started_at = datetime.now(timezone.utc) - timedelta(hours=1)
    repo.commit()
    queue = QueueManager(repo.session)
    assert queue.metrics()["stuck"] == 1
    assert len(queue.list_messages(status=EmailStatus.SENDING, older_than_seconds=300)) == 1
    assert queue.cleanup(retention_days=30) == 1
    assert repo.get_message(msg.id) is not None
    assert queue.cleanup(retention_days=30, dry_run=False) == 1
    assert repo.session.scalar(select(func.count()).select_from(EmailAttempt)) == 1
    assert queue.inspect(pending.id)["status"] == "SENDING"


def test_operation_validation_and_missing(repo):
    queue = QueueManager(repo.session)
    with pytest.raises(MessageNotFoundError):
        queue.inspect(uuid4())
    with pytest.raises(MessageNotFoundError):
        change(queue, uuid4(), "cancel")
    for kwargs in ({"limit": 0}, {"older_than_seconds": -1}):
        with pytest.raises(ValidationError):
            queue.list_messages(**kwargs)
    with pytest.raises(ValidationError):
        queue.metrics(stuck_after_seconds=0)
    with pytest.raises(ValidationError):
        queue.cleanup(retention_days=-1)
    msg = enqueue(repo)
    with pytest.raises(ValidationError):
        queue.transition(msg.id, action="cancel", expected_attempt=0, actor="", note="")
    msg.subject = "pending"
    with pytest.raises(TransactionModeError):
        change(queue, msg.id, "cancel")
    repo.rollback()


def test_async_queue_api(tmp_path):
    async def run():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'queue.db'}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                repo = AsyncEmailRepository(session)
                msg = await AsyncEmailService(repo).enqueue(
                    to=["a@example.com"], subject="Hi", text="body", idempotency_key="async"
                )
                queue = AsyncQueueManager(session)
                assert len(await queue.list_messages()) == 1
                assert (await queue.metrics())["due"] == 1
                await queue.transition(
                    msg.id, action="cancel", expected_attempt=0, actor="ops", note="test"
                )
                assert (await queue.inspect(msg.id))["status"] == "CANCELLED"
                assert await queue.cleanup(retention_days=0, dry_run=False) == 1
                assert await repo.cleanup_sent(0) == 0
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_unexpected_backend_exception_requires_reconciliation(repo):
    msg = enqueue(repo)

    class Broken:
        name = "console"

        def send(self, message):
            raise RuntimeError("private token")

    service = EmailService(repo, backend=Broken())
    assert service.send_now(msg.id).status == EmailStatus.SENDING
    data = QueueManager(repo.session).inspect(msg.id)
    assert data["attempts"][0]["error_code"] == "backend_exception"
    assert data["attempts"][0]["outcome"] == "UNKNOWN"
    assert "private" not in msg.last_error_message
