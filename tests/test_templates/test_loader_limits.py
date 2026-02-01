from __future__ import annotations

import pytest

from fastapi_post_office.templates.loader import TemplateLoadError, load_template_dir


def test_loader_size_limit(tmp_path):
    tdir = tmp_path / "t"
    tdir.mkdir()
    (tdir / "manifest.json").write_text(
        "{\"name\":\"t\",\"revision\":1,\"description\":\"t\",\"required_vars\":[]}",
        encoding="utf-8",
    )
    (tdir / "subject.j2").write_text("x" * 50, encoding="utf-8")
    (tdir / "text.j2").write_text("x" * 50, encoding="utf-8")

    with pytest.raises(TemplateLoadError):
        load_template_dir(tdir, max_bytes=10)
