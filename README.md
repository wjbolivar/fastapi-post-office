# FastAPI Post Office 📬

![CI](https://github.com/wjbolivar/fastapi-post-office/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Coverage](https://img.shields.io/badge/coverage-87.32%25-brightgreen.svg)


FastAPI Post Office is a production-ready email delivery library for FastAPI and Python applications.

It brings Django Post Office–level reliability to the FastAPI ecosystem by combining file-based, versioned templates with database persistence, Celery-powered async delivery, retry policies, and pluggable email providers.

---

## ✨ Key Features

- 📄 File-based, versioned templates (Git as source of truth)
- 🧠 Secure Jinja2 template rendering (sandboxed, strict variables)
- 📨 Persistent email message lifecycle (queued, sent, retrying, failed)
- ⚙️ Celery-powered async delivery with deterministic retry policies
- 🔌 Pluggable email backends (Console, SMTP, SES, SendGrid, Postmark, SendPulse)
- 🧷 Suppression list and webhook parsing (bounces/complaints)
- 🔐 Secure by default (no sensitive logs, header injection protection)
- 🧪 High test coverage (target ≥ 85–90%)

---

## 🧱 Architecture Overview

```
Application
   ↓
FastAPI Post Office
   ├── EmailService
   ├── Template Renderer
   ├── Message Repository (SQLAlchemy)
   ├── Email Backends
   ├── Celery Tasks
   └── CLI (sync-templates)
```

- Core is synchronous for predictability
- Celery handles async delivery
- ORM: SQLAlchemy 2.x

---

## 📁 Template Structure

Templates live in your repository and are synced into the database.

```
templates/
  welcome_user/
    manifest.json
    subject.j2
    html.j2
    text.j2
```

### manifest.json example

```json
{
  "name": "welcome_user",
  "revision": 2,
  "description": "Welcome email after signup",
  "required_vars": ["first_name"],
  "tags": ["auth", "onboarding"]
}
```

Rules:
- Revisions must increase monotonically
- Content changes without revision bumps will fail
- Templates are validated before syncing

---

## 📦 Installation

### Base install

```bash
pip install fastapi-post-office
```

### With optional extras

```bash
# SMTP backend
pip install "fastapi-post-office[smtp]"

# Celery integration
pip install "fastapi-post-office[celery]"

# Admin UI
pip install "fastapi-post-office[admin]"

# Dev tooling (tests, lint, format)
pip install "fastapi-post-office[dev]"

# All extras
pip install "fastapi-post-office[all]"
```

---

## 🚀 Basic Usage

### Enqueue an email using a template

```python
await fapo.enqueue_template(
    template_name="welcome_user",
    to=["user@example.com"],
    context={"first_name": "William"},
    idempotency_key="welcome_user:user:123"
)
```

### Enqueue a raw email

```python
await fapo.enqueue(
    to=["user@example.com"],
    subject="Hello",
    html="<b>Hello</b>",
    text="Hello"
)
```

### Send immediately (without Celery)

```python
await fapo.send_now(message_id)
```

---

## ⚡ Quickstart (end-to-end)

1) **Set env vars**

```env
FAPO_DATABASE_URL=sqlite+pysqlite:///./fapo.db
FAPO_EMAIL_BACKEND=console
FAPO_DEFAULT_FROM=no-reply@example.com
```

2) **Sync templates**

```bash
fapo sync-templates --path ./templates --upsert
```

3) **Enqueue a message**

```python
from fastapi_post_office import EmailService
from fastapi_post_office.db import create_engine_from_url, create_session_factory, EmailRepository
from fastapi_post_office.config import settings

engine = create_engine_from_url(settings.database_url)
session = create_session_factory(engine)()
repo = EmailRepository(session)
service = EmailService(repo)

service.enqueue_template(
    template_name="welcome_user",
    to=["user@example.com"],
    context={"first_name": "William"},
    idempotency_key="welcome_user:user:123",
)
```

4) **Send immediately**

```python
message_id = service.enqueue(
    to=["user@example.com"],
    subject="Hello",
    html="<b>Hello</b>",
    text="Hello",
    idempotency_key="raw:user:123",
).id

service.send_now(message_id)
```

5) **Async with Celery (optional)**

```env
FAPO_CELERY_BROKER_URL=redis://localhost:6379/0
```

```python
from fastapi_post_office.tasks.send import send_message

send_message.delay(str(message_id))
```

---

## ⚙️ Configuration

Configuration is done via environment variables (prefix `FAPO_`) or by overriding
`fastapi_post_office.config.Settings`. Key settings:

### Core

```env
FAPO_ENV=development
FAPO_DATABASE_URL=sqlite+pysqlite:///./fapo.db
FAPO_EMAIL_BACKEND=console
FAPO_DEFAULT_FROM=no-reply@example.com
```

### SMTP backend

```env
FAPO_EMAIL_BACKEND=smtp
FAPO_SMTP_HOST=smtp.example.com
FAPO_SMTP_PORT=587
FAPO_SMTP_USERNAME=your_user
FAPO_SMTP_PASSWORD=your_pass
FAPO_SMTP_STARTTLS=true
```

### SES (via SMTP)

```env
FAPO_EMAIL_BACKEND=ses
FAPO_SMTP_HOST=email-smtp.us-east-1.amazonaws.com
FAPO_SMTP_USERNAME=your_ses_user
FAPO_SMTP_PASSWORD=your_ses_pass
```

### SendGrid

```env
FAPO_EMAIL_BACKEND=sendgrid
FAPO_SENDGRID_API_KEY=your_sendgrid_key
FAPO_SENDGRID_BASE_URL=https://api.sendgrid.com/v3/mail/send
```

### Postmark

```env
FAPO_EMAIL_BACKEND=postmark
FAPO_POSTMARK_SERVER_TOKEN=your_postmark_token
FAPO_POSTMARK_BASE_URL=https://api.postmarkapp.com/email
```

### SendPulse

```env
FAPO_EMAIL_BACKEND=sendpulse
FAPO_SENDPULSE_API_TOKEN=your_sendpulse_token
FAPO_SENDPULSE_BASE_URL=https://api.sendpulse.com/smtp/emails
FAPO_SENDPULSE_FROM_NAME="Your App"
```

### Celery

```env
FAPO_CELERY_BROKER_URL=redis://localhost:6379/0
FAPO_CELERY_BACKEND_URL=redis://localhost:6379/1
```

### Suppression list

```env
FAPO_BLOCK_SUPPRESSED=true
```

---

## 🔁 Retry Policy

Default retry schedule:

| Attempt | Delay |
|--------|-------|
| 1 | Immediate |
| 2 | +60 seconds |
| 3 | +120 seconds |
| 4 | Mark as FAILED |

Retry behavior is configurable via environment variables.

---

## 🛠 CLI — Sync Templates

Templates are synced using the CLI:

```bash
fapo sync-templates --path ./templates --upsert
```

This command:
- Validates template manifests
- Computes source hashes
- Performs safe upserts
- Fails fast on inconsistencies

Ideal for CI/CD and production deployments.

---

## 🧷 Providers API

Register custom providers:

```python
from fastapi_post_office import register_provider
from fastapi_post_office.backends.base import EmailBackend, SendResult


class CustomBackend(EmailBackend):
    name = "custom"

    def send(self, message):
        return SendResult(ok=True, provider_message_id="custom")


register_provider("custom", CustomBackend, override=True)
```

---

## 🪝 Webhooks (bounces / complaints)

Parse events and store in suppression list:

```python
from fastapi_post_office import parse_suppression_events
from fastapi_post_office.db import EmailRepository, SuppressionReason

events = parse_suppression_events("sendgrid", payload)
for email, reason, meta in events:
    repo.add_suppression(email, reason, provider="sendgrid", metadata=meta)
    repo.commit()
```

---

## 🧑‍💻 Admin (Development Only)

An optional admin interface can be enabled for development and inspection:

- Disabled by default
- Fail-fast if misconfigured in production
- Intended only for debugging and inspection

---

## 🔐 Security

- Jinja2 sandboxed rendering
- No email bodies logged by default
- No template context persisted unless explicitly enabled
- Header injection prevention
- Credentials loaded only from environment variables

---

## 🧪 Testing & Quality

- pytest-based test suite
- SQLite in-memory database for tests
- Celery eager mode for deterministic behavior
- Target coverage: ≥ 85%

### Run tests

```bash
pytest
```

### Lint / format / type-check

```bash
ruff check fastapi_post_office tests
black --check fastapi_post_office tests
mypy fastapi_post_office
```

---

## 📄 License

MIT

---

## ⭐ Why FastAPI Post Office?

Email is infrastructure, not an afterthought.

FastAPI Post Office gives you predictability, safety, and production confidence for transactional email delivery in FastAPI projects.
