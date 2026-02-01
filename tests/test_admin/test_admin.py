from __future__ import annotations

from fastapi_post_office.admin.mount import mount_admin
from fastapi_post_office.config import settings


def test_mount_admin_disabled():
    settings.admin_mode = "disabled"
    mount_admin(app=None, engine=None)


def test_mount_admin_with_fake_sqladmin(monkeypatch):
    class FakeAdmin:
        def __init__(self, app, engine):
            self.app = app
            self.engine = engine

        def add_view(self, view):
            return None

    class FakeModelView:
        def __init_subclass__(cls, **kwargs):
            return None

    fake_module = type("sqladmin", (), {"Admin": FakeAdmin, "ModelView": FakeModelView})
    monkeypatch.setitem(__import__("sys").modules, "sqladmin", fake_module)

    settings.admin_mode = "local_only"
    mount_admin(app=object(), engine=object())


def test_mount_admin_dev_public_in_production():
    settings.env = "production"
    settings.admin_mode = "dev_public"
    try:
        mount_admin(app=object(), engine=object())
    except RuntimeError:
        pass
    finally:
        settings.env = "development"
        settings.admin_mode = "disabled"
