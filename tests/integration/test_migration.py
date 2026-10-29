import pytest

from fastapi_post_office.db import Base
from tests.test_migrations.test_upgrade import exercise_upgrade

pytestmark = pytest.mark.integration


def test_postgres_upgrade_preserves_data(postgres):
    engine, _ = postgres
    # The fixture owns a unique disposable schema, never application tables.
    Base.metadata.drop_all(engine)
    exercise_upgrade(engine)
