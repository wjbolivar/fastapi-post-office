from __future__ import annotations

import asyncio

import pytest

from fastapi_post_office.backends.base import SendResult
from fastapi_post_office.db.models import EmailMessage, EmailStatus, EmailTemplate
from fastapi_post_office.service.async_email_service import AsyncEmailService
from fastapi_post_office.service.idempotency import IdempotencyError


class FakeAsyncRepo:
    def __init__(self):
        self.messages = {}
        self.template = None
        self.suppressed = set()

    async def get_template(self, name: str, active_only: bool = True):
        return self.template

    async def get_message(self, message_id):
        return self.messages.get(message_id)

    async def get_message_by_idempotency(self, key: str):
        return self.messages.get(key)

    async def create_message(self, message: EmailMessage):
        self.messages[message.id] = message
        return message

    async def commit(self):
        return None

    async def flush(self):
        return None

    async def set_status(self, message, status, **kwargs):
        message.status = status
        return message

    async def increment_attempt(self, message):
        message.attempt_count += 1
        return message

    async def is_suppressed(self, email: str) -> bool:
        return email in self.suppressed


class DummyBackend:
    name = "dummy"

    def send(self, message):
        return SendResult(ok=True, provider_message_id="dummy")


def _run(coro):
    return asyncio.run(coro)


def test_async_service_missing_idempotency_key():
    repo = FakeAsyncRepo()
    service = AsyncEmailService(repo)
    service.backend = DummyBackend()
    with pytest.raises(IdempotencyError):
        _run(
            service.enqueue(
                to=["user@example.com"],
                subject="Hi",
                html="<b>Hi</b>",
                text=None,
                idempotency_key="",
            )
        )


def test_async_service_enqueue_template_and_suppression():
    repo = FakeAsyncRepo()
    service = AsyncEmailService(repo)
    service.backend = DummyBackend()

    # set template properly
    repo.template = EmailTemplate(
        name="welcome_user",
        revision=1,
        subject_template="Hi",
        html_template=None,
        text_template="Hi",
        required_vars_json=[],
        content_policy_json=None,
        tags_json=[],
        source_hash="hash",
        is_active=True,
    )

    message = _run(
        service.enqueue_template(
            template_name="welcome_user",
            to=["user@example.com"],
            context={},
            idempotency_key="k1",
        )
    )
    assert message.status == EmailStatus.QUEUED

    repo.suppressed.add("blocked@example.com")
    with pytest.raises(ValueError):
        _run(
            service.enqueue(
                to=["blocked@example.com"],
                subject="Hi",
                html="<b>Hi</b>",
                text=None,
                idempotency_key="k2",
            )
        )


def test_async_service_send_now():
    repo = FakeAsyncRepo()
    service = AsyncEmailService(repo)
    service.backend = DummyBackend()

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
    )
    repo.messages[message.id] = message

    sent = _run(service.send_now(message.id))
    assert sent.status == EmailStatus.SENT


def test_async_service_send_now_missing_message():
    repo = FakeAsyncRepo()
    service = AsyncEmailService(repo)
    service.backend = DummyBackend()
    with pytest.raises(ValueError):
        _run(service.send_now("missing"))


def test_async_service_retry_then_fail():
    class FailingBackend:
        name = "fail"

        def send(self, message):
            return SendResult(ok=False, error_message="boom")

    repo = FakeAsyncRepo()
    service = AsyncEmailService(repo)
    service.backend = FailingBackend()

    message = EmailMessage(
        from_email="no-reply@example.com",
        to_json=["user@example.com"],
        cc_json=[],
        bcc_json=[],
        subject="Hello",
        html_body=None,
        text_body="Hi",
        attempt_count=0,
        max_attempts=1,
        status=EmailStatus.QUEUED,
    )
    repo.messages[message.id] = message

    sent = _run(service.send_now(message.id))
    assert sent.status == EmailStatus.FAILED
