"""NCBI identity configuration.

No network: these check what the application tells NCBI about itself and,
just as importantly, that it never tells anyone else.
"""

import pytest
from Bio import Entrez

import ncbi_client
from ncbi_client import ConfigurationError


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    monkeypatch.delenv("NCBI_EMAIL", raising=False)
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    ncbi_client.reset()
    yield
    ncbi_client.reset()


# ---- identity -----------------------------------------------------------


def test_a_missing_contact_address_is_refused(monkeypatch):
    """Better a clear configuration error than an anonymous request wearing
    a placeholder name badge."""

    with pytest.raises(ConfigurationError) as raised:
        ncbi_client.configure()

    assert "NCBI_EMAIL" in str(raised.value)


def test_a_blank_contact_address_counts_as_missing(monkeypatch):
    monkeypatch.setenv("NCBI_EMAIL", "   ")

    with pytest.raises(ConfigurationError):
        ncbi_client.configure()


def test_the_address_and_tool_are_sent(monkeypatch):
    monkeypatch.setenv("NCBI_EMAIL", "someone@example.org")

    ncbi_client.configure()

    assert Entrez.email == "someone@example.org"
    assert Entrez.tool == "OriginTree"


def test_an_api_key_is_used_when_present(monkeypatch):
    monkeypatch.setenv("NCBI_EMAIL", "someone@example.org")
    monkeypatch.setenv("NCBI_API_KEY", "abc123")

    ncbi_client.configure()

    assert Entrez.api_key == "abc123"


def test_no_blank_api_key_is_sent_when_absent(monkeypatch):
    monkeypatch.setenv("NCBI_EMAIL", "someone@example.org")
    Entrez.api_key = "left over from another test"

    ncbi_client.configure()

    assert not Entrez.api_key


# ---- what the outside world may see -------------------------------------


def test_status_reports_presence_never_values(monkeypatch):
    monkeypatch.setenv("NCBI_EMAIL", "private@example.org")
    monkeypatch.setenv("NCBI_API_KEY", "SECRETKEY")

    report = ncbi_client.status()

    assert report["ncbi_email_configured"] is True
    assert report["ncbi_api_key_configured"] is True

    rendered = repr(report)
    assert "private@example.org" not in rendered
    assert "SECRETKEY" not in rendered


def test_status_works_before_configuration():
    assert ncbi_client.status()["ncbi_email_configured"] is False


# ---- the request ceiling ------------------------------------------------


def test_the_ceiling_reflects_the_identity(monkeypatch):
    monkeypatch.setenv("NCBI_EMAIL", "someone@example.org")
    assert ncbi_client.requests_per_second() == 3.0

    monkeypatch.setenv("NCBI_API_KEY", "abc123")
    assert ncbi_client.requests_per_second() == 10.0


def test_the_throttle_stays_inside_the_ceiling(monkeypatch):
    import rate_limit

    monkeypatch.setenv("NCBI_EMAIL", "someone@example.org")
    unkeyed = rate_limit._min_interval()

    monkeypatch.setenv("NCBI_API_KEY", "abc123")
    keyed = rate_limit._min_interval()

    # a key buys a higher ceiling, so the wait shortens
    assert keyed < unkeyed
    # and both stay under the documented rate, not at it
    assert unkeyed >= 1.0 / 3.0
    assert keyed >= 1.0 / 10.0


def test_configuration_is_enforced_before_any_request(monkeypatch):
    """No call path may reach NCBI unidentified."""

    import rate_limit

    with pytest.raises(ConfigurationError):
        rate_limit.wait()
