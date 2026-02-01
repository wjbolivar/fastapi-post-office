# FastAPI Post Office 📬

FastAPI Post Office is a production-ready email delivery library for FastAPI and Python applications.

It brings Django Post Office–level reliability to the FastAPI ecosystem by combining file-based, versioned templates with database persistence, Celery-powered async delivery, retry policies, and pluggable email providers.

---

## ✨ Key Features

- 📄 File-based, versioned templates (Git as source of truth)
- 🧠 Secure Jinja2 template rendering (sandboxed, strict variables)
- 📨 Persistent email message lifecycle (queued, sent, retrying, failed)
- ⚙️ Celery-powered async delivery with deterministic retry policies
- 🔌 Pluggable email backends (Console, SMTP, extensible)
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

---

## 📄 License

MIT

---

## ⭐ Why FastAPI Post Office?

Email is infrastructure, not an afterthought.

FastAPI Post Office gives you predictability, safety, and production confidence for transactional email delivery in FastAPI projects.
