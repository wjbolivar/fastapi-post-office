"""Upgrade the 0.1 schema to 0.2; call inside an Alembic upgrade transaction.

Stop workers first. SQLite and PostgreSQL are supported. No destructive downgrade
is supplied: rolling back history/claim data requires an operator-approved plan.
The schema below is intentionally frozen, independent of future ORM changes.
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    Uuid,
    inspect,
    text,
)
from sqlalchemy.engine import Connection
from sqlalchemy.schema import CreateColumn


def upgrade(connection: Connection) -> None:
    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("The 0.2 migration is validated only for SQLite and PostgreSQL")
    inspector = inspect(connection)
    if not inspector.has_table("email_messages"):
        raise RuntimeError(
            "Expected the 0.1 schema; create initial schema with Alembic metadata first"
        )
    if dialect == "postgresql":
        connection.execute(text("ALTER TYPE email_status ADD VALUE IF NOT EXISTS 'CANCELLED'"))
    existing = {c["name"] for c in inspector.get_columns("email_messages")}
    for column in (
        Column("sending_started_at", DateTime(timezone=True), nullable=True),
        Column("completed_at", DateTime(timezone=True), nullable=True),
        Column("claim_token", Uuid(), nullable=True),
    ):
        if column.name not in existing:
            ddl = str(CreateColumn(column).compile(dialect=connection.dialect))
            connection.execute(text(f"ALTER TABLE email_messages ADD COLUMN {ddl}"))
    metadata = MetaData()
    messages = Table(
        "email_messages",
        metadata,
        Column("id", Uuid(), primary_key=True),
        Column("status", String(32)),
        Column("next_attempt_at", DateTime(timezone=True)),
    )
    Index("ix_email_messages_due", messages.c.status, messages.c.next_attempt_at).create(
        connection, checkfirst=True
    )
    attempts = Table(
        "email_attempts",
        metadata,
        Column("id", Uuid(), primary_key=True),
        Column(
            "message_id",
            Uuid(),
            ForeignKey("email_messages.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column("number", Integer, nullable=False),
        Column("claim_token", Uuid(), unique=True, nullable=False),
        Column("provider", String(64)),
        Column("started_at", DateTime(timezone=True), nullable=False),
        Column("finished_at", DateTime(timezone=True)),
        Column("duration_ms", Integer),
        Column("outcome", String(32), nullable=False),
        Column("error_code", String(64)),
        Column("provider_message_id", String(255)),
        UniqueConstraint("message_id", "number", name="uq_email_attempt_number"),
    )
    events = Table(
        "email_events",
        metadata,
        Column("id", Uuid(), primary_key=True),
        Column(
            "message_id",
            Uuid(),
            ForeignKey("email_messages.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column("action", String(32), nullable=False),
        Column("actor", String(255), nullable=False),
        Column("note", String(1000), nullable=False),
        Column(
            "created_at",
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    attempts.create(connection, checkfirst=True)
    events.create(connection, checkfirst=True)
    connection.execute(
        text(
            "UPDATE email_messages SET completed_at = sent_at WHERE status = 'SENT' AND completed_at IS NULL"
        )
    )
