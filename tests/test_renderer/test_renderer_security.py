from __future__ import annotations

import pytest

from fastapi_post_office.templates.loader import load_templates
from fastapi_post_office.templates.renderer import RenderError, render_template


def test_render_header_injection(template_dir):
    source = load_templates(template_dir, max_bytes=10_000)[0]
    with pytest.raises(RenderError):
        render_template(source, {"first_name": "Ana\nBcc: x"}, strict=True, max_bytes=10_000)
