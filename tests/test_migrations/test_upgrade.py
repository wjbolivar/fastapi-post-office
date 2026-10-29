from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import MetaData, create_engine, inspect, select
from sqlalchemy.orm import Session

from fastapi_post_office import EmailService
from fastapi_post_office.db import Base, EmailMessage, EmailRepository
from fastapi_post_office.migrations import upgrade_0_2
from fastapi_post_office.queue import QueueManager


def legacy_metadata():
    metadata = MetaData()
    for name in ("email_messages", "email_templates", "email_suppressions"):
        table = Base.metadata.tables[name].to_metadata(metadata)
        if name == "email_messages":
            for field in ("sending_started_at", "completed_at", "claim_token"):
                table._columns.remove(table.c[field])
            table.c.status.type.enums = ["QUEUED", "SENDING", "SENT", "RETRYING", "FAILED"]
            table.indexes.clear()
    return metadata


def exercise_upgrade(engine):
    legacy = legacy_metadata()
    legacy.create_all(engine)
    saved_id = uuid4()
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(
            legacy.tables["email_messages"]
            .insert()
            .values(
                id=saved_id,
                from_email="a@example.com",
                to_json=["b@example.com"],
                cc_json=[],
                bcc_json=[],
                subject="Keep",
                text_body="Body",
                status="SENT",
                sent_at=now,
                attempt_count=1,
                max_attempts=3,
            )
        )
    with engine.begin() as conn:
        upgrade_0_2(conn)
    # Repeat is safe for deployment retries.
    with engine.begin() as conn:
        upgrade_0_2(conn)
    assert {"email_attempts", "email_events"} <= set(inspect(engine).get_table_names())
    with Session(engine) as session:
        saved = session.get(EmailMessage, saved_id)
        assert saved.subject == "Keep" and saved.completed_at is not None
        repo = EmailRepository(session)
        msg = EmailService(repo).enqueue(
            to=["b@example.com"], subject="New", text="Body", idempotency_key="migrated"
        )
        data = QueueManager(session).transition(
            msg.id,
            action="cancel",
            expected_attempt=0,
            actor="migration-test",
            note="enum accepts cancellation",
        )
        assert data["status"] == "CANCELLED"
        assert len(session.scalars(select(EmailMessage)).all()) == 2


def test_sqlite_upgrade_preserves_data(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'legacy.db'}")
    try:
        exercise_upgrade(engine)
    finally:
        engine.dispose()
