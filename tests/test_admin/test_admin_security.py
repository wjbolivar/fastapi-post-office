import pytest
from sqladmin.authentication import AuthenticationBackend
from starlette.applications import Starlette
from starlette.testclient import TestClient

from fastapi_post_office.admin.mount import mount_admin
from fastapi_post_office.config import settings


def test_secured_admin_requires_authentication(db_session):
    settings.admin_mode = "secured"
    with pytest.raises(RuntimeError, match="authentication_backend"):
        mount_admin(Starlette(), db_session.bind)


def test_secured_admin_rejects_anonymous_requests(db_session):
    class Deny(AuthenticationBackend):
        async def authenticate(self, request):
            return False

    settings.admin_mode = "secured"
    app = Starlette()
    mount_admin(app, db_session.bind, authentication_backend=Deny(secret_key="test-only"))
    with TestClient(app) as client:
        response = client.get("/admin/", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"].endswith("/admin/login")


@pytest.mark.parametrize("host,status", [("192.0.2.1", 403), ("127.0.0.1", 200), ("::1", 200)])
def test_local_only_admin_checks_peer_not_forwarded_header(db_session, host, status):
    settings.admin_mode = "local_only"
    app = Starlette()
    mount_admin(app, db_session.bind)
    with TestClient(app, client=(host, 1234)) as client:
        assert client.get("/admin/", headers={"X-Forwarded-For": "127.0.0.1"}).status_code == status


def test_local_only_forbidden_in_production(db_session):
    settings.admin_mode = "local_only"
    settings.env = "production"
    with pytest.raises(RuntimeError, match="secured"):
        mount_admin(Starlette(), db_session.bind)


def test_public_admin_requires_explicit_opt_in(db_session):
    settings.admin_mode = "dev_public"
    with pytest.raises(RuntimeError, match="explicit opt-in"):
        mount_admin(Starlette(), db_session.bind)
