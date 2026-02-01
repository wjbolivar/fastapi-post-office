from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TemplateManifest:
    name: str
    revision: int
    description: str
    required_vars: list[str]
    tags: list[str]
    content_policy: dict[str, Any] | None


class ManifestError(ValueError):
    pass


def load_manifest(path: Path) -> TemplateManifest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Invalid JSON in manifest: {path}") from exc

    for key in ("name", "revision", "description", "required_vars"):
        if key not in data:
            raise ManifestError(f"Missing required field '{key}' in manifest: {path}")

    name = str(data["name"]).strip()
    if not name:
        raise ManifestError("Manifest name must not be empty")

    try:
        revision = int(data["revision"])
    except (TypeError, ValueError) as exc:
        raise ManifestError("Manifest revision must be an integer") from exc
    if revision < 1:
        raise ManifestError("Manifest revision must be >= 1")

    description = str(data["description"]).strip()
    required_vars = list(data.get("required_vars", []))
    tags = list(data.get("tags", []))
    content_policy = data.get("content_policy")

    if not isinstance(required_vars, list):
        raise ManifestError("required_vars must be a list")
    if not all(isinstance(x, str) and x.strip() for x in required_vars):
        raise ManifestError("required_vars must be a list of non-empty strings")
    if not isinstance(tags, list):
        raise ManifestError("tags must be a list")

    return TemplateManifest(
        name=name,
        revision=revision,
        description=description,
        required_vars=required_vars,
        tags=tags,
        content_policy=content_policy,
    )
