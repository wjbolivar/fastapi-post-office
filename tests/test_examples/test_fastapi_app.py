import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from examples.fastapi_app.app import BusinessBase, Signup, create_app
from fastapi_post_office.db import Base, EmailMessage, EmailRepository, EmailTemplate


@pytest.mark.parametrize("template_exists", [True, False])
def test_signup_commits_business_and_email_together(tmp_path, template_exists):
    path = tmp_path / "app.db"
    engine = create_engine(f"sqlite+pysqlite:///{path}")
    Base.metadata.create_all(engine)
    BusinessBase.metadata.create_all(engine)
    if template_exists:
        with Session(engine) as session:
            EmailRepository(session).upsert_template(
                EmailTemplate(
                    name="welcome",
                    revision=1,
                    subject_template="Hi {{ first_name }}",
                    text_template="Body",
                    required_vars_json=["first_name"],
                    tags_json=[],
                    source_hash="test",
                )
            )
            session.commit()
    app = create_app(f"sqlite+aiosqlite:///{path}")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/signup",
            json={"request_id": "signup-1", "email": "a@example.com", "first_name": "Ana"},
        )
        assert response.status_code == (201 if template_exists else 500)
        if template_exists:
            repeated = client.post(
                "/signup",
                json={"request_id": "signup-1", "email": "a@example.com", "first_name": "Ana"},
            )
            assert repeated.status_code == 201
            assert repeated.json()["signup_id"] == response.json()["signup_id"]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Signup)) == int(template_exists)
        assert session.scalar(select(func.count()).select_from(EmailMessage)) == int(
            template_exists
        )
    engine.dispose()
