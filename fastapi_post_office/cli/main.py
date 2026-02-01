from __future__ import annotations

import typer

from .sync_templates import sync_templates_command

app = typer.Typer(add_completion=False)


@app.command("sync-templates")
def sync_templates(
    path: str = typer.Option(..., "--path", help="Templates root path"),
    upsert: bool = typer.Option(False, "--upsert", help="Upsert templates"),
) -> None:
    sync_templates_command(path=path, upsert=upsert)
