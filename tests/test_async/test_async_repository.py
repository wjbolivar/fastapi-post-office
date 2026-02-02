from __future__ import annotations

import asyncio

from fastapi_post_office.db.async_repository import AsyncEmailRepository
from fastapi_post_office.db.models import (
    EmailMessage,
    EmailStatus,
    EmailTemplate,
    SuppressionReason,
)


class FakeResult:
    def __init__(self, scalar=None, scalars_list=None, rowcount=None):
        self._scalar = scalar
        self._scalars_list = scalars_list or []
        self.rowcount = rowcount

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._scalars_list


class FakeAsyncSession:
    def __init__(self, results):
        self._results = list(results)
        self.added = []
        self.added_all = []
        self.executed = 0

    async def execute(self, stmt):
        self.executed += 1
        return self._results.pop(0)

    async def get(self, model, message_id):
        return self._results.pop(0).scalar_one_or_none()

    def add(self, item):
        self.added.append(item)

    def add_all(self, items):
        self.added_all.extend(items)

    async def commit(self):
        return None

    async def rollback(self):
        return None

    async def flush(self):
        return None


def test_async_repository_methods():
    template = EmailTemplate(
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

    results = [
        FakeResult(scalar=None),  # upsert -> get_template
        FakeResult(scalars_list=[message]),  # list_due_messages
        FakeResult(rowcount=2),  # cleanup_sent
        FakeResult(scalar=object()),  # is_suppressed
        FakeResult(rowcount=1),  # remove_suppression
        FakeResult(scalar=message),  # get_message
        FakeResult(scalar=message),  # get_message_by_idempotency
    ]
    session = FakeAsyncSession(results)
    repo = AsyncEmailRepository(session)

    # get_template (None)
    assert repo

    # upsert_template should add when missing
    template_out = asyncio.run(repo.upsert_template(template))
    assert template_out is template
    assert session.added

    # list_due_messages
    due = asyncio.run(repo.list_due_messages())
    assert due

    # cleanup_sent
    deleted = asyncio.run(repo.cleanup_sent(30))
    assert deleted == 2

    # is_suppressed
    assert asyncio.run(repo.is_suppressed("a@example.com")) is True

    # remove_suppression
    asyncio.run(repo.remove_suppression("a@example.com"))

    # add_suppression
    asyncio.run(repo.add_suppression("a@example.com", SuppressionReason.BOUNCE))

    # get_message
    fetched = asyncio.run(repo.get_message("msg-id"))
    assert fetched is message

    # get_message_by_idempotency
    idem = asyncio.run(repo.get_message_by_idempotency("key"))
    assert idem is message

    # create_message / set_status / increment_attempt / bulk_add
    asyncio.run(repo.create_message(message))
    asyncio.run(repo.set_status(message, EmailStatus.SENT))
    asyncio.run(repo.increment_attempt(message))
    asyncio.run(repo.bulk_add([message]))
    asyncio.run(repo.commit())
    asyncio.run(repo.rollback())
    asyncio.run(repo.flush())
