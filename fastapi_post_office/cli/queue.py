from __future__ import annotations

import json
from contextlib import contextmanager
from uuid import UUID

import typer

from fastapi_post_office.config import settings
from fastapi_post_office.db import EmailStatus, create_engine_from_url, create_session_factory
from fastapi_post_office.exceptions import PostOfficeError
from fastapi_post_office.queue import QueueManager

app = typer.Typer(
    help="Inspect and operate the persisted queue. Output excludes bodies and recipients."
)


@contextmanager
def manager():
    engine = create_engine_from_url(settings.database_url)
    try:
        with create_session_factory(engine)() as session:
            yield QueueManager(session)
    except PostOfficeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    finally:
        engine.dispose()


def output(value):
    typer.echo(json.dumps(value, indent=2))


@app.command("list")
def list_messages(status: EmailStatus | None = None, older_than_seconds: int = 0, limit: int = 100):
    with manager() as queue:
        output(
            queue.list_messages(status=status, older_than_seconds=older_than_seconds, limit=limit)
        )


@app.command("inspect")
def inspect_message(message_id: UUID):
    with manager() as queue:
        output(queue.inspect(message_id))


@app.command("transition")
def transition(
    message_id: UUID,
    action: str,
    expected_attempt: int = typer.Option(...),
    actor: str = typer.Option(...),
    note: str = typer.Option(...),
    acknowledge_duplicate_risk: bool = False,
    additional_attempts: int = 3,
    provider_message_id: str | None = None,
):
    """Actions: cancel, retry, reconcile-sent, reconcile-failed, reconcile-retry."""
    with manager() as queue:
        output(
            queue.transition(
                message_id,
                action=action,
                expected_attempt=expected_attempt,
                actor=actor,
                note=note,
                acknowledge_duplicate_risk=acknowledge_duplicate_risk,
                additional_attempts=additional_attempts,
                provider_message_id=provider_message_id,
            )
        )


@app.command("metrics")
def metrics(stuck_after_seconds: int = 300):
    with manager() as queue:
        output(queue.metrics(stuck_after_seconds=stuck_after_seconds))


@app.command("cleanup")
def cleanup(
    retention_days: int = 30,
    include_failed: bool = False,
    execute: bool = typer.Option(False, help="Delete eligible records; default is a dry run"),
):
    with manager() as queue:
        output(
            {
                "count": queue.cleanup(
                    retention_days=retention_days,
                    include_failed=include_failed,
                    dry_run=not execute,
                ),
                "dry_run": not execute,
            }
        )
