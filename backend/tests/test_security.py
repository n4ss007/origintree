"""Response headers and the inbound request budget."""

import security
from security import SECURITY_HEADERS, _hits, _too_many


def setup_function():
    _hits.clear()


# ---- rate limiting ------------------------------------------------------


def test_requests_within_the_budget_are_allowed():
    for i in range(security.MAX_REQUESTS):
        assert _too_many("1.2.3.4", 1000.0) is False, f"blocked at request {i}"


def test_the_budget_is_enforced():
    for _ in range(security.MAX_REQUESTS):
        _too_many("1.2.3.4", 1000.0)

    assert _too_many("1.2.3.4", 1000.0) is True


def test_one_caller_cannot_spend_anothers_budget():
    for _ in range(security.MAX_REQUESTS):
        _too_many("1.2.3.4", 1000.0)

    assert _too_many("5.6.7.8", 1000.0) is False


def test_the_window_slides():
    for _ in range(security.MAX_REQUESTS):
        _too_many("1.2.3.4", 1000.0)

    assert _too_many("1.2.3.4", 1000.0) is True
    # once the window has passed, the budget is available again
    assert _too_many("1.2.3.4", 1000.0 + security.WINDOW_SECONDS + 1) is False


def test_the_table_does_not_grow_without_bound():
    for i in range(5000):
        _too_many(f"10.0.{i // 256}.{i % 256}", 1000.0)

    assert len(_hits) <= 4096


# ---- headers ------------------------------------------------------------


def test_scripts_are_restricted_to_this_origin():
    csp = SECURITY_HEADERS["Content-Security-Policy"]

    assert "script-src 'self'" in csp
    # an inline-script escape hatch would defeat the point
    assert "script-src 'self' 'unsafe-inline'" not in csp


def test_the_page_cannot_be_framed():
    assert "frame-ancestors 'none'" in SECURITY_HEADERS["Content-Security-Policy"]
    assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"


def test_content_types_are_not_sniffed():
    assert SECURITY_HEADERS["X-Content-Type-Options"] == "nosniff"


def test_no_other_host_can_be_contacted():
    csp = SECURITY_HEADERS["Content-Security-Policy"]

    assert "default-src 'self'" in csp
    assert "connect-src 'self'" in csp
    assert "object-src 'none'" in csp


def test_hardware_permissions_are_denied():
    policy = SECURITY_HEADERS["Permissions-Policy"]

    for feature in ("geolocation", "microphone", "camera"):
        assert f"{feature}=()" in policy
