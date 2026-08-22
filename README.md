# OriginTree

Search an organism and see where it sits in the tree of life.

## What it does

OriginTree looks an organism up in NCBI Taxonomy and draws the branch that
leads to it, from the root of the record down to the species. You can compare
two organisms to see how much classification they share and where their paths
separate, and read a short stretch of their real COX1 DNA barcode.

The repository also holds the research side of the project: pipelines that
build multi-marker phylogenies with MAFFT and IQ-TREE, a fossil calibration
set, and a worked Panthera example.

## Features

- Search by common or scientific name, with results ranked by how well the
  name actually matches
- Ambiguous names (like "panda") show every organism that genuinely has that
  name instead of guessing
- Animated lineage tree — key ranks by default, or every step in the record
- Compare two organisms: shared ranks, the point they diverge, and a fossil
  age for the shared clade where one exists
- DNA barcode comparison: aligns each organism's COX1 record and reports how
  much of it matches
- An 8-base window of real barcode sequence, read from GenBank

## Tech

- **Backend** — Python, FastAPI, Biopython
- **Frontend** — plain HTML, CSS and ES modules (no build step, no framework)
- **Research pipelines** — MAFFT, IQ-TREE, BEAST, SQLite
- **Data** — NCBI Taxonomy, GenBank, GBIF

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

uvicorn main:app --reload --app-dir backend
```

Then open <http://127.0.0.1:8000>. The server serves the site as well as the
API, so that one command runs the whole thing.

NCBI asks callers to identify themselves, so set a contact address first —
without it the API returns a clear configuration error rather than guessing:

```bash
set NCBI_EMAIL=you@example.com   # macOS/Linux: export NCBI_EMAIL=...
```

A free [NCBI API key](https://account.ncbi.nlm.nih.gov/settings/) is optional
locally and worth having in production, where the outbound address is shared
with everything else on the platform:

```bash
set NCBI_API_KEY=your-key        # never commit this
```

Every setting the project reads is listed in `.env.example`; copy it to `.env`
and fill in what you need.

`GET /api/health` reports whether each is configured — presence only, never
the values. `GET /api/health?check=upstream` additionally tries one real NCBI
lookup and reports what came back, which is how to tell a misconfigured
deployment from an unreachable one.

Tests:

```bash
python -m pytest backend/tests -q
```

The research pipelines are separate command-line tools and need MAFFT and
IQ-TREE installed:

```bash
python backend/evolution_pipeline.py
python backend/multimarker_pipeline.py
```

## Hosting it

Set these before exposing the server to the internet:

| Variable | Why |
| --- | --- |
| `NCBI_EMAIL` | **Required.** NCBI needs a contact address; the API refuses to start a lookup without one |
| `NCBI_API_KEY` | Strongly recommended in production. Raises NCBI's limit from 3 to 10 requests a second, counted against the key rather than the shared server address |
| `ORIGINTREE_ALLOWED_ORIGINS` | Your domain. Defaults to localhost only |
| `ORIGINTREE_HTTPS=1` | Sends HSTS. Only set this once you actually serve HTTPS |
| `ORIGINTREE_RATE_LIMIT` | API requests per client per minute (default 60) |
| `ORIGINTREE_NCBI_TIMEOUT` | Seconds before an outbound NCBI call gives up (default 15) |
| `ORIGINTREE_DOCS=off` | Optional — withdraws `/docs` and `/openapi.json` |

Run without `--reload` in production, add `--no-server-header` so the server
does not announce itself, and put it behind a TLS-terminating proxy:

```bash
uvicorn main:app --app-dir backend --host 0.0.0.0 --port 8000 --no-server-header
```

The rate limiter counts per client address in memory, so if you run more than
one instance each keeps its own count.

## Data

Classification and lineages come from **NCBI Taxonomy**, and every DNA base
shown is read from a real **GenBank** record — nothing is generated. **GBIF**
is used for one thing only: turning an everyday name into a scientific one
when NCBI has no vernacular entry for it.

Fossil calibrations live in `data/fossils.csv`, each with the paper it came
from. It is small and hand-curated, so a fossil age only appears for a clade
that actually has a row.

## Contributors

- **Nandana Ani Sindhu** — [GitHub](https://github.com/n4ss007) · [LinkedIn](https://www.linkedin.com/in/nandanaanisindhu/)
- **BRGOVIND** — [GitHub](https://github.com/BRGOVIND)
