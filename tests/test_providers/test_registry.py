from __future__ import annotations

import pytest

from fastapi_post_office.backends import get_backend
from fastapi_post_office.backends.base import EmailBackend, SendResult
from fastapi_post_office.providers import register_provider, registry


class DummyBackend(EmailBackend):
    name = "dummy"

    def send(self, message):
        return SendResult(ok=True, provider_message_id="dummy")


def test_register_and_create_provider():
    register_provider("dummy", DummyBackend, override=True)
    backend = registry.create("dummy")
    assert isinstance(backend, DummyBackend)


def test_register_duplicate_raises():
    register_provider("dummy2", DummyBackend, override=True)
    with pytest.raises(ValueError):
        register_provider("dummy2", DummyBackend)


def test_get_backend_uses_registry():
    register_provider("dummy3", DummyBackend, override=True)
    backend = get_backend("dummy3")
    assert isinstance(backend, DummyBackend)
