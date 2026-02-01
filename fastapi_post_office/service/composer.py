from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi_post_office.templates.loader import TemplateSource
from fastapi_post_office.templates.renderer import RenderedTemplate, render_template


@dataclass(frozen=True)
class ComposedEmail:
    template_name: str
    template_revision: int
    subject: str
    html_body: str | None
    text_body: str | None


def compose_from_template(
    source: TemplateSource,
    context: dict[str, Any],
    strict: bool,
    max_bytes: int,
) -> ComposedEmail:
    rendered: RenderedTemplate = render_template(source, context, strict=strict, max_bytes=max_bytes)
    return ComposedEmail(
        template_name=source.manifest.name,
        template_revision=source.manifest.revision,
        subject=rendered.subject,
        html_body=rendered.html,
        text_body=rendered.text,
    )
