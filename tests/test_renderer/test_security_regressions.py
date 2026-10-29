from dataclasses import replace

import pytest

from fastapi_post_office.templates.loader import load_templates
from fastapi_post_office.templates.renderer import RenderError, render_template


def test_html_escapes_variables_but_text_does_not(template_dir):
    source = load_templates(template_dir, max_bytes=10_000)[0]
    result = render_template(source, {"first_name": '<img src="x">'}, strict=True, max_bytes=10_000)
    assert "<img" not in result.html
    assert "&lt;img" in result.html
    assert "<img" in result.text
    assert "<img" in result.subject


def test_non_strict_undefined_variables(template_dir):
    source = load_templates(template_dir, max_bytes=10_000)[0]
    source = replace(source, text_template="{{ optional }}")
    assert render_template(source, {"first_name": "Ana"}, strict=False, max_bytes=10_000).text == ""


@pytest.mark.parametrize(
    "template", ["{{ ''.__class__.__mro__ }}", "{{ cycler.__init__.__globals__.os }}"]
)
def test_sandbox_blocks_python_access(template_dir, template):
    source = replace(load_templates(template_dir, max_bytes=10_000)[0], html_template=template)
    with pytest.raises(RenderError):
        render_template(source, {"first_name": "Ana"}, strict=True, max_bytes=10_000)
