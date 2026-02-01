from __future__ import annotations

from datetime import datetime

from fastapi_post_office.backends.base import SendResult
from fastapi_post_office.db.models import EmailMessage, EmailStatus
from fastapi_post_office.service import EmailService


class FailingBackend:
    name = "fail"

    def send(self, message):
        return SendResult(ok=False, error_message="boom")


def test_retry_flow(repo):
    message = EmailMessage(
        from_email="no-reply@example.com",
        to_json=["user@example.com"],
        cc_json=[],
        bcc_json=[],
        subject="Hello",
        html_body="<b>Hi</b>",
        text_body="Hi",
        attempt_count=0,
        max_attempts=2,
    )
    repo.create_message(message)
    repo.commit()

    service = EmailService(repo)
    service.backend = FailingBackend()
    result = service.send_now(message.id)

    assert result.status == EmailStatus.RETRYING
    assert result.attempt_count == 1
    assert result.next_attempt_at is not None
