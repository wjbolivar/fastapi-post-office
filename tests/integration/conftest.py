import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from fastapi_post_office.db import Base


@pytest.fixture()
def postgres():
    url = os.environ.get("FAPO_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set FAPO_TEST_POSTGRES_URL for real PostgreSQL integration")
    schema = "fapo_test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    isolated_url = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(isolated_url)
    Base.metadata.create_all(engine)
    try:
        yield engine, isolated_url.render_as_string(hide_password=False)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
