"""Turn an everyday animal name into scientific names worth looking up.

NCBI Taxonomy is excellent at scientific names and patchy at vernacular ones.
It has no entry at all for "seahorse", and the only thing it calls "panda" is
a West African tree. That is not a bug in NCBI — its name index simply is not
a vernacular dictionary.

GBIF does maintain a large vernacular index, so this module asks GBIF one
question only: "what scientific names do people call this?". Every taxonomic
fact the site displays still comes from NCBI. GBIF never contributes lineage,
rank or identifiers, and if it is unreachable the search still works with
NCBI's own results.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from ranking import PLURAL, normalize, score_name

GBIF_SEARCH = "https://api.gbif.org/v1/species/search"
USER_AGENT = "OriginTree/1.0 (taxonomy lookup)"

# GBIF orders by its own relevance, which is not useful here: asking it for
# "lion" puts the Lion Anole lizard first. We pull a wide page and re-rank it
# ourselves on exact vernacular matches.
PAGE_SIZE = 100
REQUEST_TIMEOUT = 12


def _get(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.load(response)


def _vernacular_names(record) -> list:
    return [
        entry.get("vernacularName", "")
        for entry in record.get("vernacularNames", [])
        if entry.get("vernacularName")
    ]


def resolve_vernacular(term: str, limit: int = 6) -> list:
    """Find scientific names whose vernacular names match `term`.

    Returns a list of dicts with `scientific_name`, the `vernacular` that
    matched and the GBIF `rank`/`kingdom`, best first. Only exact and
    plural-level vernacular matches count; anything looser produces the sort
    of noise we are trying to remove.

    Never raises. A failure here degrades the search, it does not break it.
    """

    term = normalize(term)

    if not term:
        return []

    query = urllib.parse.urlencode(
        {
            "q": term,
            "qField": "VERNACULAR",
            "status": "ACCEPTED",
            "limit": PAGE_SIZE,
        }
    )

    try:
        payload = _get(f"{GBIF_SEARCH}?{query}")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return []

    matches = []

    for record in payload.get("results", []):
        scientific_name = record.get("canonicalName") or record.get("scientificName")

        if not scientific_name:
            continue

        best_score = 0
        best_vernacular = ""

        for vernacular in _vernacular_names(record):
            score = score_name(term, vernacular)

            if score > best_score:
                best_score = score
                best_vernacular = vernacular

        # Only a name someone actually uses for this organism counts. A
        # partial overlap is how "lion" reaches Anolis lionotus.
        if best_score < PLURAL:
            continue

        matches.append(
            {
                "scientific_name": scientific_name,
                "vernacular": best_vernacular,
                "rank": (record.get("rank") or "").lower(),
                "kingdom": record.get("kingdom") or "",
                "score": best_score,
            }
        )

    matches.sort(key=lambda m: (m["score"], m["rank"] == "species"), reverse=True)

    # One entry per scientific name, keeping the strongest vernacular.
    seen = set()
    unique = []

    for match in matches:
        key = normalize(match["scientific_name"])

        if key in seen:
            continue

        seen.add(key)
        unique.append(match)

    return unique[:limit]


__all__ = ["resolve_vernacular"]
