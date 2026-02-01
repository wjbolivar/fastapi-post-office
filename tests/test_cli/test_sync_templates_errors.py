from __future__ import annotations

import pytest

from fastapi_post_office.cli.sync_templates import SyncError, sync_templates_command
from fastapi_post_office.config import settings
from fastapi_post_office.db import Base, create_engine_from_url


def _make_template(root, revision: int, subject: str):
    tdir = root / "welcome_user"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "manifest.json").write_text(
        f'{{"name":"welcome_user","revision":{revision},"description":"Welcome","required_vars":["first_name"]}}',
        encoding="utf-8",
    )
    (tdir / "subject.j2").write_text(subject, encoding="utf-8")
    (tdir / "text.j2").write_text("Hi", encoding="utf-8")


def test_sync_templates_revision_lower(template_dir, tmp_path):
    db_url = f"sqlite+pysqlite:///{tmp_path / 'cli_err.db'}"
    settings.database_url = db_url
    engine = create_engine_from_url(db_url)
    Base.metadata.create_all(engine)
    try:
        # First sync revision 2
        _make_template(template_dir, revision=2, subject="Hi")
        sync_templates_command(path=str(template_dir), upsert=True)

        # Now try revision 1
        _make_template(template_dir, revision=1, subject="Hi")
        with pytest.raises(SyncError):
            sync_templates_command(path=str(template_dir), upsert=True)
    finally:
        engine.dispose()


def test_sync_templates_hash_changed_without_revision(template_dir, tmp_path):
    db_url = f"sqlite+pysqlite:///{tmp_path / 'cli_err2.db'}"
    settings.database_url = db_url
    engine = create_engine_from_url(db_url)
    Base.metadata.create_all(engine)
    try:
        _make_template(template_dir, revision=1, subject="Hi")
        sync_templates_command(path=str(template_dir), upsert=True)

        # change subject without revision bump
        _make_template(template_dir, revision=1, subject="Hi changed")
        with pytest.raises(SyncError):
            sync_templates_command(path=str(template_dir), upsert=True)
    finally:
        engine.dispose()
