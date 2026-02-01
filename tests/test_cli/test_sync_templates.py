from __future__ import annotations

from fastapi_post_office.cli.sync_templates import sync_templates_command
from fastapi_post_office.db import Base, EmailRepository, create_engine_from_url, create_session_factory
from fastapi_post_office.config import settings


def test_sync_templates_command(template_dir, tmp_path):
    db_url = f"sqlite+pysqlite:///{tmp_path / 'cli.db'}"
    settings.database_url = db_url
    engine = create_engine_from_url(db_url)
    Base.metadata.create_all(engine)

    sync_templates_command(path=str(template_dir), upsert=True)

    session = create_session_factory(engine)()
    repo = EmailRepository(session)
    template = repo.get_template("welcome_user", active_only=False)
    assert template is not None
    session.close()
    engine.dispose()
