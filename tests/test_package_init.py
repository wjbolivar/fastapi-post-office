from __future__ import annotations

import fastapi_post_office as fapo


def test_package_lazy_exports():
    assert fapo.EmailService is not None
    assert fapo.register_provider is not None
    assert fapo.parse_suppression_events is not None
