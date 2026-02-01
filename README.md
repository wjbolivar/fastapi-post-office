# FastAPI Post Office 📬

![CI](https://github.com/wjbolivar/fastapi-post-office/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Coverage](https://img.shields.io/badge/coverage-88%25-brightgreen.svg)

---

## Overview

**FastAPI Post Office** is a production-grade library for managing **transactional email delivery**
in FastAPI and Python applications.

It treats email as **core infrastructure**, not as a side-effect, combining:

- file-based, versioned templates (Git as source of truth)
- database-backed message lifecycle
- Celery-powered asynchronous delivery
- deterministic retry policies
- pluggable email providers



---

## Why FastAPI Post Office?

Most email libraries focus only on *sending* messages.

FastAPI Post Office focuses on the **entire lifecycle**:

- What was sent?
- When?
- Using which template version?
- Did it fail? Was it retried?
- Can it be audited or reproduced later?

This makes it suitable for **real production systems**, regulated environments,
and long-running platforms where email delivery must be predictable and traceable.

---

## Key Features

- **Versioned templates (Git-first)**
  - Templates live in your repository
  - Synced into the database via CLI
  - Fully reproducible and auditable

- **Secure template rendering**
  - Jinja2 sandboxed environment
  - Strict variable validation
  - Header injection protection

- **Persistent message lifecycle**
  - Status tracking: queued, sending, sent, retrying, failed
  - Idempotency guarantees
  - Retry scheduling stored in the database

- **Asynchronous delivery**
  - Optional Celery integration
  - Deterministic retry policy (default: 0s, 60s, 120s)
  - Periodic retry and cleanup tasks

- **Pluggable providers**
  - Console backend (development)
  - SMTP backend (generic)
  - Designed for SES, SendGrid, Postmark, Mailgun

- **High code quality**
  - Strict typing (mypy)
  - Formatting (black)
  - Linting (ruff)
  - Enforced test coverage (≥ 85%)

---

## Architecture Overview

```
Application
   ↓
FastAPI Post Office
   ├── EmailService (public API)
   ├── Template Renderer
   ├── Repository (SQLAlchemy)
   ├── Email Backends
   ├── Celery Tasks (optional)
   └── CLI (sync-templates)
```

- Core logic is synchronous and deterministic
- Asynchronous behavior is delegated to Celery
- ORM: SQLAlchemy 2.x

---

## Template System

Templates are stored as files and treated as the **source of truth**.

```
templates/
  welcome_user/
    manifest.json
    subject.j2
    html.j2
    text.j2
```

### `manifest.json`

```json
{
  "name": "welcome_user",
  "revision": 2,
  "description": "Welcome email after signup",
  "required_vars": ["first_name"],
  "tags": ["auth", "onboarding"]
}
```

**Rules**

- `revision` must increase monotonically
- Content changes without a revision bump fail fast
- Templates are validated before syncing

---

## Basic Usage

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

## Retry Policy

Default retry schedule:

| Attempt | Delay |
|--------|-------|
| 1 | Immediate |
| 2 | +60 seconds |
| 3 | +120 seconds |
| 4 | Mark as FAILED |

Retry behavior is configurable via environment variables.

---

## CLI — Sync Templates

Templates are synced into the database using a CLI command:

```bash
fapo sync-templates --path ./templates --upsert
```

The command:

- validates template manifests
- computes content hashes
- performs safe upserts
- fails fast on inconsistencies

Designed for CI/CD and production deployments.

---

## Development & Admin

An optional admin interface is available **for development only**:

- disabled by default
- protected by environment checks
- intended for inspection and debugging

It is not required for production operation.

---

## Security Model

- Sandboxed template rendering
- No email bodies logged by default
- Template context is not persisted unless explicitly enabled
- Credentials loaded only from environment variables
- Fail-fast checks for unsafe configurations

---

## Testing & Quality

- pytest-based test suite
- SQLite in-memory database for tests
- Celery eager mode for deterministic execution
- Enforced minimum coverage: **85%**

---

## Installation

```bash
pip install fastapi-post-office
```

Development install:

```bash
pip install -e ".[dev,smtp,celery,admin]"
```

---

## License

MIT

