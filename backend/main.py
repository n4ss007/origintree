"""OriginTree web API.

Serves the site and answers taxonomy questions against NCBI.

    uvicorn main:app --reload --app-dir backend

then open http://127.0.0.1:8000

Configuration, all optional:

    ORIGINTREE_ALLOWED_ORIGINS   comma-separated origins for CORS, default "*"
    ORIGINTREE_FRONTEND_DIR      path to the site, default ../frontend
"""

import logging
import os
import sys
from pathlib import Path

# The modules below are imported by bare name — `import validation`, not
# `from backend import validation` — which only resolves when this directory
# is on the import path. Running `uvicorn main:app --app-dir backend` puts it
# there; importing the app as `backend.main:app`, which is what a deployment
# does, does not. Adding it here makes both work without every module having
# to change.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import ncbi_client
import validation
from barcode_compare import compare_barcodes
from comparison import compare, summarize
from fossils import calibration_for_path
from models import BarcodeComparison, BarcodeWindow, Comparison, SearchResponse, SequenceResponse, Taxon
from security import rate_limit_middleware, security_headers_middleware
from sequences import fetch_barcode_window, fetch_sequence_summaries
from taxonomy import get_species, search

# The interactive docs describe a read-only public API and are genuinely
# useful for a research project, so they stay on by default. Set
# ORIGINTREE_DOCS=off to withdraw them from a deployment.
_docs_enabled = os.environ.get("ORIGINTREE_DOCS", "on").lower() not in ("off", "0", "false")

# Every handler below turns an upstream failure into a clean message for the
# caller. Without logging it first the cause vanishes entirely — a deployed
# 502 with an empty function log and nothing to go on. The message the caller
# sees stays generic; the traceback goes to the platform log.
log = logging.getLogger("origintree")

app = FastAPI(
    title="OriginTree",
    description="Trace the story of life.",
    version="2.0.0",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# The API serves the site from the same origin, so cross-origin access is not
# needed for normal use. Default to the local development hosts only; a
# deployment that needs more sets ORIGINTREE_ALLOWED_ORIGINS explicitly.
DEFAULT_ORIGINS = "http://127.0.0.1:8000,http://localhost:8000"

_origins = os.environ.get("ORIGINTREE_ALLOWED_ORIGINS", DEFAULT_ORIGINS)

app.middleware("http")(rate_limit_middleware)
app.middleware("http")(security_headers_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)



def _upstream_detail(error: Exception) -> str:
    """A short, non-sensitive description of an upstream failure, for logs.

    Names the exception and, for an HTTP error, the status NCBI returned —
    which is the difference between "we are being throttled" and "we are
    being refused". Never includes the request URL, which carries the email
    and API key as query parameters.
    """

    status = getattr(error, "code", None) or getattr(error, "status", None)
    reason = getattr(error, "reason", "")

    if status:
        return f"{type(error).__name__} status={status} reason={reason}"

    return f"{type(error).__name__}: {reason or error}"


def _upstream_failure(operation: str, error: Exception, **context) -> HTTPException:
    """Log an upstream failure and produce the response the caller sees."""

    fields = " ".join(f"{k}={v!r}" for k, v in context.items())
    log.error("%s failed: %s %s", operation, _upstream_detail(error), fields)

    # A missing contact address is our misconfiguration, not NCBI being down,
    # and saying so is the difference between a five minute fix and a hunt.
    if isinstance(error, ncbi_client.ConfigurationError):
        return HTTPException(
            status_code=503,
            detail="This deployment is not configured for NCBI access.",
        )

    return HTTPException(
        status_code=502,
        detail="NCBI did not answer. Try again in a moment.",
    )


@app.get("/api/search", response_model=SearchResponse)
def search_taxa(
    animal: str = Query(..., min_length=1, description="Common or scientific name"),
    limit: int = Query(6, ge=1, le=20, description="How many matches to return"),
):
    """Search NCBI Taxonomy, ranked so the strongest name matches come first."""

    try:
        term = validation.search_term(animal)
    except validation.InvalidInput as bad:
        raise HTTPException(status_code=400, detail=str(bad))

    try:
        return search(term, limit=limit)
    except Exception as error:
        raise _upstream_failure("search", error, query=term)


@app.get("/api/species/{taxid}", response_model=Taxon)
def species_detail(taxid: str):
    """One taxon by its NCBI TaxID."""

    try:
        taxid = validation.taxid(taxid)
    except validation.InvalidInput as bad:
        raise HTTPException(status_code=400, detail=str(bad))

    try:
        return get_species(taxid)
    except LookupError:
        raise HTTPException(status_code=404, detail=f"No record for TaxID {taxid}.")
    except Exception as error:
        raise _upstream_failure("species lookup", error, taxid=taxid)


@app.get("/api/species/{taxid}/sequences", response_model=SequenceResponse)
def species_sequences(
    taxid: str,
    gene: str = Query("COX1", description="Gene symbol to look for"),
    limit: int = Query(8, ge=1, le=20),
):
    """COX1 records held for this taxon. Loaded on demand: it is a slow call."""

    try:
        taxid = validation.taxid(taxid)
        gene = validation.gene(gene)
    except validation.InvalidInput as bad:
        raise HTTPException(status_code=400, detail=str(bad))

    try:
        return fetch_sequence_summaries(taxid, gene=gene, max_records=limit)
    except Exception as error:
        raise _upstream_failure("sequence lookup", error, taxid=taxid, gene=gene)


@app.get("/api/species/{taxid}/barcode", response_model=BarcodeWindow)
def species_barcode(taxid: str, gene: str = Query("COX1", description="Gene symbol to read")):
    """A short window of real bases from this taxon's best COX1 record."""

    try:
        taxid = validation.taxid(taxid)
        gene = validation.gene(gene)
    except validation.InvalidInput as bad:
        raise HTTPException(status_code=400, detail=str(bad))

    try:
        return fetch_barcode_window(taxid, gene=gene)
    except Exception as error:
        raise _upstream_failure("barcode read", error, taxid=taxid, gene=gene)


def _resolve(term: str) -> dict:
    """A search term or a TaxID, resolved to one taxonomy record.

    Digits are treated as a TaxID, which is exact and skips a search; a name
    goes through the ranked search and takes its best match, so comparison
    inherits the same ranking the rest of the site uses.
    """

    try:
        term = validation.taxid_or_term(term)
    except validation.InvalidInput:
        raise HTTPException(status_code=400, detail="Name two organisms to compare.")

    if term.isdigit():
        try:
            return get_species(term)
        except LookupError:
            raise HTTPException(status_code=404, detail=f"No record for TaxID {term}.")

    found = search(term, limit=1)

    if not found["results"]:
        raise HTTPException(status_code=404, detail=f"No record of “{term}” in NCBI Taxonomy.")

    return found["results"][0]


@app.get("/api/compare", response_model=Comparison)
def compare_organisms(
    a: str = Query(..., min_length=1, description="Name or TaxID of the first organism"),
    b: str = Query(..., min_length=1, description="Name or TaxID of the second organism"),
):
    """Compare two organisms: what classification they share, and where they part.

    The comparison itself is pure logic over the two records — the only slow
    part is fetching them.
    """

    taxon_a = _resolve(a)
    taxon_b = _resolve(b)

    try:
        result = compare(taxon_a, taxon_b)
    except Exception as error:
        log.error("comparison failed: %s", _upstream_detail(error))
        raise HTTPException(status_code=500, detail="Those records could not be compared.")

    return {
        "a": taxon_a,
        "b": taxon_b,
        "summary": summarize(taxon_a, taxon_b, result),
        # only present when the shared path reaches a clade that has a real
        # dated fossil in the project's dataset
        "fossil": calibration_for_path(result["shared"]),
        **result,
    }


@app.get("/api/compare/barcode", response_model=BarcodeComparison)
def compare_barcode(
    a: str = Query(..., min_length=1, description="TaxID of the first organism"),
    b: str = Query(..., min_length=1, description="TaxID of the second organism"),
    gene: str = Query("COX1", description="Gene symbol to compare"),
):
    """Align two organisms' barcodes and report how much they agree.

    Separate from /api/compare because it is slow — two record fetches plus
    an alignment — so the taxonomy comparison stays fast and this is asked
    for only when the reader wants it.
    """

    try:
        a = validation.taxid(a)
        b = validation.taxid(b)
        gene = validation.gene(gene)
    except validation.InvalidInput as bad:
        raise HTTPException(status_code=400, detail=str(bad))

    try:
        return compare_barcodes(a, b, gene=gene)
    except Exception as error:
        raise _upstream_failure("barcode comparison", error, a=a, b=b)


@app.get("/api/health")
def health(check: str = Query("", description="Set to 'upstream' to test NCBI reachability")):
    """Liveness, and whether this deployment is configured to reach NCBI.

    Reports only whether each setting is present — never its value, so the
    contact address and API key stay out of responses and logs.

    `?check=upstream` additionally makes one small NCBI request and reports
    what came back. That is the difference between diagnosing a deployment
    from the outside and guessing at it.
    """

    report = {"status": "ok", **ncbi_client.status()}

    if check != "upstream":
        return report

    try:
        get_species("9606")
        report["upstream"] = {"reachable": True, "detail": ""}
    except Exception as error:
        log.error("upstream check failed: %s", _upstream_detail(error))
        report["status"] = "degraded"
        report["upstream"] = {"reachable": False, "detail": _upstream_detail(error)}

    return report


# Serve the site itself, so one command runs the whole project. Registered
# after the API routes, which therefore take precedence.
FRONTEND = Path(
    os.environ.get("ORIGINTREE_FRONTEND_DIR")
    or Path(__file__).resolve().parent.parent / "frontend"
)

if FRONTEND.is_dir():

    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        """Serve the OriginTree 404 page for a wrong address.

        API routes keep returning JSON — a client parsing a response should
        not suddenly receive a page of HTML — so only ordinary navigation
        gets the page.
        """

        if request.url.path.startswith("/api/"):
            detail = getattr(exc, "detail", "Not found.")
            return JSONResponse(status_code=404, content={"detail": detail})

        page = FRONTEND / "404.html"

        if page.is_file():
            return FileResponse(page, status_code=404, media_type="text/html")

        return JSONResponse(status_code=404, content={"detail": "Not found."})

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        icon = FRONTEND / "assets" / "favicon.ico"

        if icon.is_file():
            return FileResponse(icon)

        raise HTTPException(status_code=404, detail="No favicon.")

    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
