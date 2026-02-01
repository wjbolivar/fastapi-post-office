from __future__ import annotations

import pytest

from fastapi_post_office.templates.manifest import ManifestError, load_manifest


def test_manifest_missing_fields(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(path)
