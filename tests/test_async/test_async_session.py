from __future__ import annotations

import pytest

from fastapi_post_office.db.session_async import create_async_engine_from_url


def test_async_engine_requires_async_driver():
    with pytest.raises(RuntimeError):
        create_async_engine_from_url("sqlite+pysqlite:///./test.db")
