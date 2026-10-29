import asyncio

import pytest
from fapo.db import AsyncEmailRepository, Base, EmailMessage, EmailRepository
from fapo.service import AsyncEmailService
from sqlalchemy import Column, Integer, MetaData, Table, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from fapo import EmailService, Settings, TransactionModeError
from fastapi_post_office.backends.base import EmailBackend, SendResult
from fastapi_post_office.config import settings


class Recorder(EmailBackend):
    name = "recorder"

    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message.subject)
        return SendResult(ok=True, provider_message_id="accepted-123")


def test_config_snapshot_and_injected_backend(repo):
    config = Settings(default_from="one@example.com", max_attempts=7)
    backend = Recorder()
    service = EmailService(repo, config=config, backend=backend)
    config.default_from = "changed@example.com"
    settings.default_from = "global@example.com"
    msg = service.enqueue(
        to=["to@example.com"], subject="Hi", text="Body", idempotency_key="config"
    )
    assert msg.from_email == "one@example.com"
    assert msg.max_attempts == 7
    service.send_now(msg.id)
    assert backend.sent == ["Hi"]


def test_outbox_rollback_and_commit_are_owned_by_application(db_session):
    # External engine/session are supported too; no library-specific transaction hooks.
    engine = db_session.bind
    table = Table("business", MetaData(), Column("id", Integer, primary_key=True))
    table.create(engine)
    for commit in (False, True):
        with Session(engine) as session:
            service = EmailService(EmailRepository(session), auto_commit=False)
            # Email is deliberately first: catches SQLite SAVEPOINT-before-BEGIN bug.
            msg = service.enqueue(
                to=["a@example.com"], subject="Hi", text="Body", idempotency_key=str(commit)
            )
            session.execute(insert(table).values(id=int(commit)))
            message_id = msg.id
            with pytest.raises(TransactionModeError):
                service.send_now(message_id)
            session.commit() if commit else session.rollback()
        with Session(engine) as check:
            assert (check.get(EmailMessage, message_id) is not None) is commit
            assert (
                check.execute(select(table).where(table.c.id == int(commit))).first() is not None
            ) is commit


def test_send_refuses_pending_changes(repo):
    service = EmailService(repo)
    msg = service.enqueue(
        to=["a@example.com"], subject="Hi", text="Body", idempotency_key="pending"
    )
    msg.subject = "uncommitted"
    with pytest.raises(TransactionModeError):
        service.send_now(msg.id)
    repo.rollback()


def test_async_outbox_rollback_and_commit(tmp_path):
    async def run():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'outbox.db'}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            for commit in (False, True):
                async with factory() as session:
                    service = AsyncEmailService(AsyncEmailRepository(session), auto_commit=False)
                    msg = await service.enqueue(
                        to=["a@example.com"], subject="Hi", text="Body", idempotency_key=str(commit)
                    )
                    message_id = msg.id
                    with pytest.raises(TransactionModeError):
                        await service.send_now(message_id)
                    await session.commit() if commit else await session.rollback()
                async with factory() as check:
                    assert (await check.get(EmailMessage, message_id) is not None) is commit
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_aliases_share_orm_classes():
    from fapo.db.models import EmailMessage as Alias

    from fastapi_post_office.db.models import EmailMessage as Original

    assert Original is Alias


def test_backend_receives_immutable_snapshot(repo):
    from dataclasses import FrozenInstanceError

    from fastapi_post_office.backends.base import EmailPayload

    class SnapshotBackend:
        name = "snapshot"

        def send(self, payload):
            assert isinstance(payload, EmailPayload)
            with pytest.raises(FrozenInstanceError):
                payload.subject = "modified"
            assert isinstance(payload.to_json, tuple)
            return SendResult(ok=True)

    service = EmailService(repo, backend=SnapshotBackend())
    msg = service.enqueue(
        to=["a@example.com"], subject="Hi", text="Body", idempotency_key="snapshot"
    )
    assert service.send_now(msg.id).status.value == "SENT"


def test_caller_flush_error_is_not_mistaken_for_email_idempotency(repo):
    from sqlalchemy.exc import IntegrityError

    service = EmailService(repo)
    service.enqueue(to=["a@example.com"], subject="First", text="Body", idempotency_key="already")
    repo.session.add(
        EmailMessage(
            from_email="a@example.com",
            to_json=["b@example.com"],
            cc_json=[],
            bcc_json=[],
            subject="Pending",
            text_body="Body",
            idempotency_key="already",
        )
    )
    transactional = EmailService(repo, auto_commit=False)
    with pytest.raises(IntegrityError):
        transactional.enqueue(
            to=["a@example.com"], subject="New", text="Body", idempotency_key="new"
        )
    repo.rollback()
    assert repo.get_message_by_idempotency("new") is None
