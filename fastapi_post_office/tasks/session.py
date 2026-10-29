from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache

from fastapi_post_office.config import settings
from fastapi_post_office.db import create_engine_from_url, create_session_factory


@lru_cache(maxsize=8)
def _session_factory(database_url: str, process_id: int):
    # PID keys ensure a prefork child never reuses its parent's connection pool.
    return create_session_factory(create_engine_from_url(database_url))


@contextmanager
def session_scope():
    factory = _session_factory(settings.database_url, os.getpid())
    with factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
