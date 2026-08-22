"""How this application identifies itself to NCBI.

NCBI asks every programmatic caller to say who it is, and enforces a request
ceiling per identity. An unidentified caller gets a low ceiling shared with
everyone else on the same address — which is fine from one laptop and not
fine from a serverless platform, where the outbound address is shared with
every other tenant on it. An API key moves the ceiling from "this IP" to
"this key", which is the difference between working and not working in
production.

Configuration lives here rather than beside each call so there is one place
that knows the rules. The values themselves come from the environment and
are never written down in the repository, never logged and never returned to
a caller: `status()` reports only whether each one is set.

The terminal scripts keep their own configuration. They are run by hand by
someone who is present, and are not part of this deployment.
"""

import os

from Bio import Entrez

# Sent with every request so NCBI can attribute traffic to this project.
TOOL = "OriginTree"

EMAIL_VAR = "NCBI_EMAIL"
API_KEY_VAR = "NCBI_API_KEY"


class ConfigurationError(RuntimeError):
    """The application is not configured to talk to NCBI."""


def _clean(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def email() -> str:
    return _clean(EMAIL_VAR)


def api_key() -> str:
    return _clean(API_KEY_VAR)


def configure() -> None:
    """Point Biopython at this deployment's NCBI identity.

    Raises ConfigurationError when no contact address is set, rather than
    inventing one. A placeholder address is an anonymous request wearing a
    name badge: it gets the anonymous ceiling, and the failure that follows
    looks like NCBI being down instead of a missing setting.
    """

    address = email()

    if not address:
        raise ConfigurationError(
            f"{EMAIL_VAR} is not set. NCBI requires a contact address for "
            "programmatic access."
        )

    Entrez.email = address
    Entrez.tool = TOOL

    key = api_key()

    # Biopython appends api_key to every request when this attribute is set.
    # Left unset rather than empty when absent, so no blank parameter is sent.
    if key:
        Entrez.api_key = key
    elif getattr(Entrez, "api_key", None):
        Entrez.api_key = None


_configured = False


def ensure_configured() -> None:
    """Configure once, before the first outbound request.

    Called from the throttle every request passes through, so no call path
    can reach NCBI unidentified — including the ones tests exercise directly.
    """

    global _configured

    if not _configured:
        configure()
        _configured = True


def reset() -> None:
    """Forget the cached configuration. For tests that change the environment."""

    global _configured
    _configured = False


def status() -> dict:
    """Whether each setting is present. Never the values themselves."""

    return {
        "ncbi_email_configured": bool(email()),
        "ncbi_api_key_configured": bool(api_key()),
        "tool": TOOL,
    }


def requests_per_second() -> float:
    """NCBI's documented ceiling for this identity.

    Ten per second with a key, three without. Both are per identity, and a
    serverless deployment cannot coordinate between invocations, so callers
    should stay well inside whichever applies.
    """

    return 10.0 if api_key() else 3.0
