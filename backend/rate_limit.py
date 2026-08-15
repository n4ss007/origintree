"""One rate limiter for every NCBI call this process makes.

NCBI asks for no more than three requests a second without an API key, and
blocks the address of anyone who ignores that.

The limit is per client, not per module, so this has to be a single shared
gate. It also has to hold a lock: FastAPI runs plain `def` endpoints in a
worker threadpool, so several requests really do execute at once, and an
unsynchronised "when did I last call?" global lets all of them read the same
timestamp and fire together.
"""

import threading
import time

# Three per second is the documented ceiling; leave a little headroom.
MIN_REQUEST_INTERVAL = 0.36

_lock = threading.Lock()
_last_request = 0.0


def wait():
    """Block until it is polite to make another NCBI request."""

    global _last_request

    # The sleep stays inside the lock on purpose. Releasing it first would
    # let every waiting thread wake, see the same timestamp and rush out
    # together, which is the behaviour this is here to prevent.
    with _lock:
        elapsed = time.monotonic() - _last_request

        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)

        _last_request = time.monotonic()
