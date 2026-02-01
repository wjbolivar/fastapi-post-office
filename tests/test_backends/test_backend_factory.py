from __future__ import annotations

import pytest

from fastapi_post_office.backends import get_backend


def test_get_backend_invalid():
    with pytest.raises(ValueError):
        get_backend("invalid")
