from __future__ import annotations

import asyncio

from fastapi_post_office.db.models import EmailMessage
from fastapi_post_office.service.idempotency import ensure_idempotency_async


class Repo:
    def __init__(self, message):
        self.message = message

    async def get_message_by_idempotency(self, key: str):
        return self.message


def test_ensure_idempotency_async_returns_existing():
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
    )
    repo = Repo(message)
    existing = asyncio.run(ensure_idempotency_async(repo, "k1"))
    assert existing is message
