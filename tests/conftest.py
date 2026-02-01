from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from fastapi_post_office.config import settings
from fastapi_post_office.db import Base, EmailRepository, create_engine_from_url, create_session_factory


@pytest.fixture()
def db_url(tmp_path: Path) -> str:
    return f"sqlite+pysqlite:///{tmp_path / 'test.db'}"


@pytest.fixture()
def db_session(db_url):
    settings.database_url = db_url
    engine = create_engine_from_url(db_url)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        yield session
        session.commit()
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def repo(db_session):
    return EmailRepository(db_session)


@pytest.fixture()
def template_dir(tmp_path: Path) -> Path:
    root = tmp_path / "templates"
    tdir = root / "welcome_user"
    tdir.mkdir(parents=True)
    (tdir / "manifest.json").write_text(
        """
        {"name":"welcome_user","revision":1,"description":"Welcome","required_vars":["first_name"],"tags":["auth"]}
        """,
        encoding="utf-8",
    )
    (tdir / "subject.j2").write_text("Hi {{ first_name }}", encoding="utf-8")
    (tdir / "html.j2").write_text("<b>Hello {{ first_name }}</b>", encoding="utf-8")
    (tdir / "text.j2").write_text("Hello {{ first_name }}", encoding="utf-8")
    return root
