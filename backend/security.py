"""Response headers and a request budget, for running this in public.

Two concerns, both about being reachable from the open internet rather than
from one laptop:

  * A browser should be told what this page is allowed to do, so a content
    injection bug cannot escalate into running someone else's script.

  * Every request here becomes one or more requests to NCBI. NCBI publishes
    a rate limit and blocks addresses that ignore it. The outbound throttle
    in rate_limit.py keeps *us* polite, but it does that by making callers
    queue — so without a limit on the way in, one caller can hold the queue
    open and lock everyone else out while we take the blame upstream.

The limiter is in-process and per-address. That suits a single instance,
which is what this project runs. Behind several instances or a proxy that
rewrites the client address, it needs replacing with something shared.
"""

import os
import threading
import time
from collections import deque

from fastapi import Request
from fastapi.responses import JSONResponse

# Requests allowed per address per window. NCBI's own ceiling is three per
# second across the whole server, so this is deliberately modest: enough for
# a person clicking around, not enough to monopolise the outbound queue.
MAX_REQUESTS = int(os.environ.get("ORIGINTREE_RATE_LIMIT", "60"))
WINDOW_SECONDS = int(os.environ.get("ORIGINTREE_RATE_WINDOW", "60"))

# Only the API is metered. Static files are cheap and never reach NCBI.
METERED_PREFIX = "/api/"

_lock = threading.Lock()
_hits = {}


def _client_key(request: Request) -> str:
    client = request.client
    return client.host if client else "unknown"


def _too_many(key: str, now: float) -> bool:
    """Sliding window: drop timestamps that have aged out, then count."""

    with _lock:
        seen = _hits.setdefault(key, deque())

        cutoff = now - WINDOW_SECONDS
        while seen and seen[0] < cutoff:
            seen.popleft()

        # Keep the table from growing without bound as addresses come and go.
        if not seen and len(_hits) > 4096:
            _hits.pop(key, None)
            _hits.clear()
            seen = _hits.setdefault(key, deque())

        if len(seen) >= MAX_REQUESTS:
            return True

        seen.append(now)
        return False


async def rate_limit_middleware(request: Request, call_next):
    """Refuse callers who exceed the budget, before any work is done."""

    if request.url.path.startswith(METERED_PREFIX):
        if _too_many(_client_key(request), time.monotonic()):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please wait a moment."},
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )

    return await call_next(request)


# The page loads its own scripts, styles, font and images and talks to no
# other host, so everything can be locked to 'self'. Inline styles are
# allowed because the interface animates by setting element.style directly;
# scripts have no such exception.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "object-src 'none'",
    ]
)

SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    # Stop a browser second-guessing a declared content type.
    "X-Content-Type-Options": "nosniff",
    # Belt and braces alongside frame-ancestors, for older browsers.
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Nothing here needs any of these.
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
}


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)

    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)

    # The Server banner cannot be removed here: uvicorn writes it at the
    # protocol layer, after this middleware has returned. Run it with
    # --no-server-header to withhold it.

    # Only meaningful over HTTPS, and only correct once the site is actually
    # served that way — so it is opt-in for deployment.
    if os.environ.get("ORIGINTREE_HTTPS", "").lower() in ("1", "true", "yes"):
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )

    return response
