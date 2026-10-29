"""Explicit local demo setup only; production schema changes belong in Alembic."""

from pathlib import Path

from fastapi_post_office.cli.sync_templates import sync_templates_command
from fastapi_post_office.config import settings
from fastapi_post_office.db import Base, create_engine_from_url

from .app import BusinessBase


def main():
    settings.database_url = "sqlite+pysqlite:///./example.db"
    engine = create_engine_from_url(settings.database_url)
    try:
        BusinessBase.metadata.create_all(engine)
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
    sync_templates_command(str(Path(__file__).parent / "templates"), upsert=True)


if __name__ == "__main__":
    main()
