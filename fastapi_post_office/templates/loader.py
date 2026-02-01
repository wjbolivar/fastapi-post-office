from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .hasher import compute_source_hash
from .manifest import ManifestError, TemplateManifest, load_manifest


@dataclass(frozen=True)
class TemplateSource:
    manifest: TemplateManifest
    subject_template: str
    html_template: str | None
    text_template: str | None
    source_hash: str


class TemplateLoadError(ValueError):
    pass


def _read_optional(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def load_template_dir(path: Path, max_bytes: int) -> TemplateSource:
    if not path.exists() or not path.is_dir():
        raise TemplateLoadError(f"Template path does not exist: {path}")

    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        raise TemplateLoadError(f"Missing manifest.json in {path}")

    try:
        manifest = load_manifest(manifest_path)
    except ManifestError as exc:
        raise TemplateLoadError(str(exc)) from exc

    subject_path = path / "subject.j2"
    if not subject_path.exists():
        raise TemplateLoadError(f"Missing subject.j2 in {path}")

    subject = subject_path.read_text(encoding="utf-8")
    html = _read_optional(path / "html.j2")
    text = _read_optional(path / "text.j2")

    if not html and not text:
        raise TemplateLoadError(f"Template must include html.j2 or text.j2 in {path}")

    size = len(subject.encode("utf-8"))
    if html:
        size += len(html.encode("utf-8"))
    if text:
        size += len(text.encode("utf-8"))
    if size > max_bytes:
        raise TemplateLoadError(f"Template size exceeds limit ({max_bytes} bytes) in {path}")

    source_hash = compute_source_hash(manifest_path, subject_path, path / "html.j2", path / "text.j2")

    return TemplateSource(
        manifest=manifest,
        subject_template=subject,
        html_template=html,
        text_template=text,
        source_hash=source_hash,
    )


def load_templates(root: Path, max_bytes: int) -> list[TemplateSource]:
    if not root.exists() or not root.is_dir():
        raise TemplateLoadError(f"Templates root does not exist: {root}")

    sources: list[TemplateSource] = []
    for child in sorted(root.iterdir()):
        if child.is_dir():
            sources.append(load_template_dir(child, max_bytes=max_bytes))
    return sources
