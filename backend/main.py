"""OriginTree web API.

Serves the site and answers taxonomy questions against NCBI.

    uvicorn main:app --reload --app-dir backend

then open http://127.0.0.1:8000

Configuration, all optional:

    ORIGINTREE_ALLOWED_ORIGINS   comma-separated origins for CORS, default "*"
    ORIGINTREE_FRONTEND_DIR      path to the site, default ../frontend
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from models import BarcodeWindow, SearchResponse, SequenceResponse, Taxon
from sequences import fetch_barcode_window, fetch_sequence_summaries
from taxonomy import get_species, search

app = FastAPI(
    title="OriginTree",
    description="Trace the story of life.",
    version="2.0.0",
)

# The API serves the site from the same origin, so cross-origin access is not
# needed for normal use. Default to the local development hosts only; a
# deployment that needs more sets ORIGINTREE_ALLOWED_ORIGINS explicitly.
DEFAULT_ORIGINS = "http://127.0.0.1:8000,http://localhost:8000"

_origins = os.environ.get("ORIGINTREE_ALLOWED_ORIGINS", DEFAULT_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/search", response_model=SearchResponse)
def search_taxa(
    animal: str = Query(..., min_length=1, description="Common or scientific name"),
    limit: int = Query(6, ge=1, le=20, description="How many matches to return"),
):
    """Search NCBI Taxonomy, ranked so the strongest name matches come first."""

    if not animal.strip():
        raise HTTPException(status_code=400, detail="Enter an organism to search for.")

    try:
        return search(animal, limit=limit)
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="NCBI did not answer. Try again in a moment.",
        )


@app.get("/api/species/{taxid}", response_model=Taxon)
def species_detail(taxid: str):
    """One taxon by its NCBI TaxID."""

    try:
        return get_species(taxid)
    except LookupError:
        raise HTTPException(status_code=404, detail=f"No record for TaxID {taxid}.")
    except Exception:
        raise HTTPException(status_code=502, detail="NCBI did not answer. Try again in a moment.")


@app.get("/api/species/{taxid}/sequences", response_model=SequenceResponse)
def species_sequences(
    taxid: str,
    gene: str = Query("COX1", description="Gene symbol to look for"),
    limit: int = Query(8, ge=1, le=20),
):
    """COX1 records held for this taxon. Loaded on demand: it is a slow call."""

    try:
        return fetch_sequence_summaries(taxid, gene=gene, max_records=limit)
    except Exception:
        raise HTTPException(status_code=502, detail="NCBI did not answer. Try again in a moment.")


@app.get("/api/species/{taxid}/barcode", response_model=BarcodeWindow)
def species_barcode(taxid: str, gene: str = Query("COX1", description="Gene symbol to read")):
    """A short window of real bases from this taxon's best COX1 record."""

    try:
        return fetch_barcode_window(taxid, gene=gene)
    except Exception:
        raise HTTPException(status_code=502, detail="NCBI did not answer. Try again in a moment.")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve the site itself, so one command runs the whole project. Registered
# after the API routes, which therefore take precedence.
FRONTEND = Path(
    os.environ.get("ORIGINTREE_FRONTEND_DIR")
    or Path(__file__).resolve().parent.parent / "frontend"
)

if FRONTEND.is_dir():

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        icon = FRONTEND / "assets" / "favicon.ico"

        if icon.is_file():
            return FileResponse(icon)

        raise HTTPException(status_code=404, detail="No favicon.")

    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
