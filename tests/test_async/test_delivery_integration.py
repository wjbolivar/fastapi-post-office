import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from fastapi_post_office.backends.base import SendResult
from fastapi_post_office.db import Base
from fastapi_post_office.db.async_repository import AsyncEmailRepository
from fastapi_post_office.db.models import EmailMessage, EmailStatus, SuppressionReason
from fastapi_post_office.service.async_email_service import AsyncEmailService


def test_async_delivery_with_real_database(tmp_path):
    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'async.db'}")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                repo = AsyncEmailRepository(session)
                service = AsyncEmailService(repo)
                msg = await service.enqueue(
                    to=["user@example.com"],
                    subject="Hi",
                    html=None,
                    text="Body",
                    idempotency_key=" key ",
                )
                duplicate = await service.enqueue(
                    to=["user@example.com"],
                    subject="Hi",
                    html=None,
                    text="Body",
                    idempotency_key="key",
                )
                assert duplicate.id == msg.id
                conflict = EmailMessage(
                    from_email=msg.from_email,
                    to_json=msg.to_json,
                    cc_json=[],
                    bcc_json=[],
                    subject="other",
                    idempotency_key="key",
                )
                assert (await repo.create_message(conflict)).id == msg.id
                assert len(await repo.list_due_messages(limit=1)) == 1

                class Failure:
                    name = "console"

                    def send(self, message):
                        return SendResult(
                            ok=False, error_message="Temporary failure", error_code="temporary"
                        )

                service.backend = Failure()
                assert (await service.send_now(msg.id)).status == EmailStatus.RETRYING
                assert msg.attempt_count == 1
                assert "private" not in msg.last_error_message
                await service.send_now(msg.id)
                assert msg.attempt_count == 1
                msg.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                await repo.commit()

                class Success:
                    name = "console"

                    def send(self, message):
                        return SendResult(ok=True)

                service.backend = Success()
                assert (await service.send_now(msg.id)).status == EmailStatus.SENT
                await service.send_now(msg.id)
                assert msg.attempt_count == 2
                blocked = await service.enqueue(
                    to=["blocked@example.com"],
                    subject="Hi",
                    html=None,
                    text="Body",
                    idempotency_key="blocked",
                )
                await repo.add_suppression("blocked@example.com", SuppressionReason.BOUNCE)
                await repo.commit()
                assert (await service.send_now(blocked.id)).status == EmailStatus.FAILED
        finally:
            await engine.dispose()

    asyncio.run(scenario())
