from __future__ import annotations

from pathlib import Path

import typer

from fastapi_post_office.config import settings
from fastapi_post_office.db import EmailRepository, EmailTemplate, create_engine_from_url, create_session_factory
from fastapi_post_office.templates.loader import TemplateLoadError, load_templates


class SyncError(RuntimeError):
    pass


def _template_from_source(source) -> EmailTemplate:
    return EmailTemplate(
        name=source.manifest.name,
        revision=source.manifest.revision,
        subject_template=source.subject_template,
        html_template=source.html_template,
        text_template=source.text_template,
        required_vars_json=source.manifest.required_vars,
        content_policy_json=source.manifest.content_policy,
        tags_json=source.manifest.tags,
        source_hash=source.source_hash,
        is_active=True,
    )


def sync_templates_command(path: str, upsert: bool) -> None:
    root = Path(path)
    try:
        sources = load_templates(root, max_bytes=settings.max_template_bytes)
    except TemplateLoadError as exc:
        raise SyncError(str(exc)) from exc

    engine = create_engine_from_url(settings.database_url)
    session_factory = create_session_factory(engine)
    session = session_factory()
    repo = EmailRepository(session)

    try:
        for source in sources:
            existing = repo.get_template(source.manifest.name, active_only=False)
            if existing:
                if source.manifest.revision < existing.revision:
                    raise SyncError(
                        f"Template {source.manifest.name} revision is lower than DB"
                    )
                if source.manifest.revision == existing.revision and source.source_hash != existing.source_hash:
                    raise SyncError(
                        f"Template {source.manifest.name} changed without revision bump"
                    )
                if not upsert:
                    continue

            repo.upsert_template(_template_from_source(source))
        repo.commit()
    except Exception:
        repo.rollback()
        raise
    finally:
        session.close()
        engine.dispose()

    typer.echo("Templates synced successfully")
