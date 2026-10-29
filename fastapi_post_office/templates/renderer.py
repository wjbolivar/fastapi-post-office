from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jinja2 import StrictUndefined, Undefined
from jinja2.exceptions import TemplateError
from jinja2.sandbox import SandboxedEnvironment

from fastapi_post_office.exceptions import ValidationError

from .loader import TemplateSource


class RenderError(ValidationError):
    pass


@dataclass(frozen=True)
class RenderedTemplate:
    subject: str
    html: str | None
    text: str | None


def _check_header_injection(value: str, field: str) -> None:
    if "\n" in value or "\r" in value:
        raise RenderError(f"Header injection detected in {field}")


def render_template(
    source: TemplateSource,
    context: dict[str, Any],
    strict: bool,
    max_bytes: int,
) -> RenderedTemplate:
    missing = [key for key in source.manifest.required_vars if key not in context]
    if missing:
        raise RenderError(f"Missing required vars: {sorted(missing)}")

    env = SandboxedEnvironment(undefined=StrictUndefined if strict else Undefined, autoescape=False)

    try:
        subject = env.from_string(source.subject_template).render(**context)
        html = None
        if source.html_template is not None:
            html_env = env.overlay(autoescape=True)
            html = html_env.from_string(source.html_template).render(**context)
        text = None
        if source.text_template is not None:
            text = env.from_string(source.text_template).render(**context)
    except TemplateError as exc:
        raise RenderError(f"Template rendering failed: {exc}") from exc

    _check_header_injection(subject, "subject")

    size = len(subject.encode("utf-8"))
    if html:
        size += len(html.encode("utf-8"))
    if text:
        size += len(text.encode("utf-8"))
    if size > max_bytes:
        raise RenderError(f"Rendered template exceeds size limit ({max_bytes} bytes)")

    return RenderedTemplate(subject=subject, html=html, text=text)
