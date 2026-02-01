from __future__ import annotations

import importlib
import sys

import pytest


def test_celery_app_requires_broker_or_dependency():
    sys.modules.pop("celery", None)
    celery_app = importlib.import_module("fastapi_post_office.tasks.celery_app")
    from fastapi_post_office.config import settings

    settings.celery_broker_url = None
    try:
        import celery  # noqa: F401

        expected = "FAPO_CELERY_BROKER_URL"
    except Exception:
        expected = "Celery is not installed"

    with pytest.raises(RuntimeError) as exc:
        celery_app.get_celery_app()
    assert expected in str(exc.value)


def test_tasks_with_fake_celery(monkeypatch):
    class FakeCelery:
        def __init__(self, *args, **kwargs):
            self.conf = type("Conf", (), {})()

        def task(self, *args, **kwargs):
            def decorator(fn):
                fn.delay = lambda *a, **k: fn(*a, **k)
                return fn

            return decorator

    fake_module = type("celery", (), {"Celery": FakeCelery})
    monkeypatch.setitem(sys.modules, "celery", fake_module)

    celery_app_module = importlib.import_module("fastapi_post_office.tasks.celery_app")
    importlib.reload(celery_app_module)

    # Configure settings to avoid broker error
    from fastapi_post_office.config import settings

    settings.celery_broker_url = "memory://"
    settings.celery_backend_url = None

    app = celery_app_module.get_celery_app()
    assert app is not None

    send_module = importlib.import_module("fastapi_post_office.tasks.send")
    periodic_module = importlib.import_module("fastapi_post_office.tasks.periodic")

    importlib.reload(send_module)
    importlib.reload(periodic_module)

    assert send_module.send_message is not None
    assert periodic_module.retry_due_messages is not None

    tasks_pkg = importlib.import_module("fastapi_post_office.tasks")
    importlib.reload(tasks_pkg)
    assert tasks_pkg.send_message is not None
