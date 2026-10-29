from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fastapi_post_office import EmailService
from fastapi_post_office.backends.base import SendResult
from fastapi_post_office.db import EmailAttempt, EmailMessage, EmailRepository, EmailStatus

pytestmark = pytest.mark.integration


def test_postgres_concurrent_idempotency(postgres):
    engine, _ = postgres
    barrier = Barrier(4)

    def enqueue():
        with Session(engine) as session:
            repo = EmailRepository(session)
            original = repo.get_message_by_idempotency

            def synchronized(key):
                found = original(key)
                if found is None:
                    barrier.wait(timeout=10)
                return found

            repo.get_message_by_idempotency = synchronized
            msg = EmailService(repo).enqueue(
                to=["a@example.com"], subject="Hi", text="body", idempotency_key="shared"
            )
            return msg.id

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: enqueue(), range(4)))
    assert len(set(ids)) == 1
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(EmailMessage)) == 1


def test_postgres_workers_only_one_delivery(postgres):
    engine, _ = postgres
    with Session(engine) as session:
        msg_id = (
            EmailService(EmailRepository(session))
            .enqueue(to=["a@example.com"], subject="Hi", text="body", idempotency_key="delivery")
            .id
        )
    entered, release = Event(), Event()
    calls = []

    class Blocking:
        name = "console"

        def send(self, msg):
            calls.append(msg.id)
            entered.set()
            assert release.wait(10)
            return SendResult(ok=True)

    def worker():
        with Session(engine) as session:
            return (
                EmailService(EmailRepository(session), backend=Blocking()).send_now(msg_id).status
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        first = pool.submit(worker)
        try:
            assert entered.wait(10)
            others = [pool.submit(worker) for _ in range(3)]
            assert all(f.result(timeout=10) == EmailStatus.SENDING for f in others)
        finally:
            release.set()
        assert first.result(timeout=10) == EmailStatus.SENT
    assert calls == [msg_id]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(EmailAttempt)) == 1
