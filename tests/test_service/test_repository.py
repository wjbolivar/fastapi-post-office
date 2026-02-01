from __future__ import annotations

from fastapi_post_office.db.models import EmailMessage, EmailStatus, EmailTemplate


def test_repository_upsert_template(repo):
    template = EmailTemplate(
        name="t",
        revision=1,
        subject_template="Hi",
        html_template=None,
        text_template="Hi",
        required_vars_json=[],
        content_policy_json=None,
        tags_json=[],
        source_hash="h1",
        is_active=True,
    )
    repo.upsert_template(template)
    repo.commit()

    template2 = EmailTemplate(
        name="t",
        revision=2,
        subject_template="Hi2",
        html_template=None,
        text_template="Hi2",
        required_vars_json=[],
        content_policy_json=None,
        tags_json=[],
        source_hash="h2",
        is_active=True,
    )
    repo.upsert_template(template2)
    repo.commit()

    stored = repo.get_template("t", active_only=False)
    assert stored is not None
    assert stored.revision == 2


def test_repository_set_status(repo):
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
    repo.create_message(message)
    repo.commit()

    repo.set_status(message, EmailStatus.SENT, provider_message_id="x")
    repo.commit()
    assert message.status == EmailStatus.SENT


def test_repository_due_and_cleanup(repo):
    from datetime import datetime, timedelta, timezone

    due_message = EmailMessage(
        from_email="no-reply@example.com",
        to_json=["user@example.com"],
        cc_json=[],
        bcc_json=[],
        subject="Hello",
        html_body=None,
        text_body="Hi",
        attempt_count=0,
        max_attempts=3,
        status=EmailStatus.RETRYING,
        next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    sent_message = EmailMessage(
        from_email="no-reply@example.com",
        to_json=["user@example.com"],
        cc_json=[],
        bcc_json=[],
        subject="Hello",
        html_body=None,
        text_body="Hi",
        attempt_count=1,
        max_attempts=3,
        status=EmailStatus.SENT,
        sent_at=datetime.now(timezone.utc) - timedelta(days=40),
    )
    repo.bulk_add([due_message, sent_message])
    repo.commit()

    due = repo.list_due_messages()
    assert len(due) >= 1

    deleted = repo.cleanup_sent(retention_days=30)
    assert deleted >= 1
