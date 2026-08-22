"""One rate limiter for every NCBI call this process makes.

NCBI asks for no more than three requests a second without an API key, and
blocks the address of anyone who ignores that.

The limit is per client, not per module, so this has to be a single shared
gate. It also has to hold a lock: FastAPI runs plain `def` endpoints in a
worker threadpool, so several requests really do execute at once, and an
unsynchronised "when did I last call?" global lets all of them read the same
timestamp and fire together.
"""

import os
import socket
import threading
import time

# NCBI's ceiling depends on identity: three requests a second unidentified,
# ten with an API key. Both are per identity rather than per process, and
# separate serverless invocations cannot see each other's timing — so this
# deliberately spends only part of the allowance, leaving room for the other
# invocations that may be running at the same time.
SAFETY_FRACTION = 0.5


def _min_interval() -> float:
    import ncbi_client

    return 1.0 / (ncbi_client.requests_per_second() * SAFETY_FRACTION)

# Biopython's Entrez helpers take no timeout, so an unanswered connection
# blocks until the platform kills the whole request — which is a 502 with no
# explanation rather than a handled error. A default socket timeout gives
# every outbound call a ceiling, so a stalled NCBI fails as an exception the
# API can turn into a real message.
NCBI_TIMEOUT_SECONDS = float(os.environ.get("ORIGINTREE_NCBI_TIMEOUT", "15"))

socket.setdefaulttimeout(NCBI_TIMEOUT_SECONDS)

_lock = threading.Lock()
_last_request = 0.0


def wait():
    """Block until it is polite to make another NCBI request."""

    global _last_request

    # The sleep stays inside the lock on purpose. Releasing it first would
    # let every waiting thread wake, see the same timestamp and rush out
    # together, which is the behaviour this is here to prevent.
    import ncbi_client

    # Every outbound NCBI request passes through here, which makes it the one
    # place guaranteed to run first — so identity is settled here too.
    ncbi_client.ensure_configured()

    with _lock:
        minimum = _min_interval()
        elapsed = time.monotonic() - _last_request

        if elapsed < minimum:
            time.sleep(minimum - elapsed)

        _last_request = time.monotonic()
