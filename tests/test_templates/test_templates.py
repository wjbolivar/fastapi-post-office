from __future__ import annotations

import pytest

from fastapi_post_office.templates.loader import TemplateLoadError, load_template_dir


def test_load_template_dir_ok(template_dir):
    tdir = template_dir / "welcome_user"
    source = load_template_dir(tdir, max_bytes=10_000)
    assert source.manifest.name == "welcome_user"
    assert source.source_hash


def test_load_template_missing_subject(tmp_path):
    tdir = tmp_path / "x"
    tdir.mkdir()
    (tdir / "manifest.json").write_text(
        '{"name":"x","revision":1,"description":"x","required_vars":[]}',
        encoding="utf-8",
    )
    with pytest.raises(TemplateLoadError):
        load_template_dir(tdir, max_bytes=10_000)
