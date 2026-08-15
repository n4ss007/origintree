"""Searching NCBI Taxonomy, and getting a sensible answer back.

The interesting work is in choosing what to ask NCBI. Its search applies
automatic term mapping, which is helpful when it works and silently wrong
when it does not:

    "sea horse"  ->  horse[All Names]   ->  Equus caballus, the actual horse
    "panda*"     ->  panda OR pandaceae OR pandalidae OR pandanus OR ...

Quoting the term stops the first. Refusing to lead with a wildcard stops the
second. What remains is handled by gathering candidates from several precise
queries and ranking them ourselves.
"""

import rate_limit
from Bio import Entrez

from name_resolver import resolve_vernacular
import ncbi_test  # noqa: F401  — importing this configures Entrez.email and .tool
from ranking import (
    MAJOR_RANKS,
    best_match,
    collapse_spaces,
    is_ambiguous,
    name_alignment,
    normalize,
    plural_forms,
    rank_candidates,
)

MAX_CANDIDATES = 24


def _esearch(term: str, retmax: int = 20) -> list:
    """One taxonomy search. Returns the taxids NCBI matched.

    Failures deliberately propagate. A search that finds nothing comes back
    as an empty IdList, not an exception, so an exception here means NCBI did
    not answer — and reporting that as "no such organism" would state a
    falsehood about the record.
    """

    rate_limit.wait()

    handle = Entrez.esearch(db="taxonomy", term=term, retmax=retmax)
    result = Entrez.read(handle)
    handle.close()

    return list(result.get("IdList", []))


def _efetch(taxids: list) -> list:
    if not taxids:
        return []

    rate_limit.wait()

    handle = Entrez.efetch(db="taxonomy", id=",".join(taxids), retmode="xml")
    records = Entrez.read(handle)
    handle.close()

    return list(records)


def _quoted(term: str) -> str:
    """Phrase-match a term so NCBI cannot drop half of it."""

    return '"{}"[All Names]'.format(term.replace('"', ""))


def build_queries(term: str, resolved_names: list) -> list:
    """The ladder of NCBI queries to try, most precise first.

    Each rung is (query, vernacular_hint). The hint travels with the query
    rather than being matched back by name afterwards: NCBI often answers a
    GBIF-supplied name with a record spelled slightly differently — an
    authority suffix, or the subfamily for a genus — and re-matching on the
    name would throw away the very hint that found the record.
    """

    queries = []
    seen = set()

    def add(query, hint=""):
        if query and query not in seen:
            seen.add(query)
            queries.append((query, hint))

    normalized = normalize(term)

    add(_quoted(term))

    for form in sorted(plural_forms(normalized)):
        if form != normalized:
            add(_quoted(form))

    collapsed = collapse_spaces(term)
    if collapsed and collapsed != normalized:
        add(_quoted(collapsed))

    for match in resolved_names:
        add(_quoted(match["scientific_name"]), match["vernacular"])

    return queries


def _ncbi_vernacular_names(record) -> list:
    """The everyday names NCBI itself records for a taxon.

    Deliberately excludes the scientific name and anything GBIF supplied, so
    it can answer one narrow question: does the source of truth agree that
    people call this organism by the searched name?
    """

    other = record.get("OtherNames", {})

    names = []

    if other.get("GenbankCommonName"):
        names.append(("common name", other["GenbankCommonName"]))

    for common in other.get("CommonName", []):
        names.append(("common name", common))

    for synonym in other.get("Synonym", []):
        names.append(("synonym", synonym))

    for equivalent in other.get("EquivalentName", []):
        names.append(("equivalent name", equivalent))

    return names


def _names_for_scoring(record, vernacular_hint: str = "") -> list:
    """Every name NCBI holds for a record, labelled for the interface."""

    names = [("scientific name", record.get("ScientificName", ""))]
    names.extend(_ncbi_vernacular_names(record))

    if vernacular_hint:
        names.append(("common name via GBIF", vernacular_hint))

    return names


def _common_name(record) -> str:
    other = record.get("OtherNames", {})

    if other.get("GenbankCommonName"):
        return other["GenbankCommonName"]

    common_names = other.get("CommonName", [])

    return common_names[0] if common_names else ""


def _other_names(record) -> list:
    other = record.get("OtherNames", {})

    collected = []

    for key in ("CommonName", "Synonym", "EquivalentName", "Includes"):
        collected.extend(str(value) for value in other.get(key, []))

    genbank = other.get("GenbankCommonName")

    # the headline common name is shown separately, so keep it out of the list
    return [name for name in dict.fromkeys(collected) if name != genbank]


def _kingdom(record) -> str:
    """The broad group a record sits in, read from its own lineage."""

    lineage = record.get("Lineage", "")

    for group in ("Viruses", "Viridiplantae", "Fungi", "Bacteria", "Archaea", "Metazoa"):
        if group in lineage:
            return group

    for node in record.get("LineageEx", []):
        if node.get("Rank") in ("kingdom", "superkingdom", "domain"):
            return str(node.get("ScientificName", ""))

    return ""


def _lineage(record) -> list:
    """The full path from the root of the record down to the organism.

    Unranked ancestors are kept. NCBI leaves a great many steps unranked —
    for some groups, nearly all of them — so dropping them would silently
    shorten the lineage and make the site's "show all N steps" a lie. They
    are marked minor instead, and the interface folds them away by default.
    """

    return [
        {
            "name": str(node.get("ScientificName", "")),
            "rank": str(node.get("Rank", "")) or "no rank",
            "taxid": str(node.get("TaxId", "")),
            "major": str(node.get("Rank", "")) in MAJOR_RANKS,
        }
        for node in record.get("LineageEx", [])
    ]


def build_result(record, query: str, vernacular_hint: str = "", source: str = "ncbi") -> dict:
    """Everything the interface needs about one taxon, from one NCBI record."""

    genetic_code = record.get("GeneticCode", {})

    score, reason, label = best_match(query, _names_for_scoring(record, vernacular_hint))

    # Separates equally-exact matches that GBIF supplied. Both a bear and a
    # West African tree answer to "panda", but only the bear is called that
    # by NCBI, which is a real signal about which one the person meant.
    corroboration, _, _ = best_match(query, _ncbi_vernacular_names(record))

    return {
        "taxid": str(record.get("TaxId", "")),
        "scientific_name": str(record.get("ScientificName", "")),
        "common_name": _common_name(record),
        "other_names": _other_names(record),
        "rank": str(record.get("Rank", "")) or "no rank",
        "division": str(record.get("Division", "")),
        "genetic_code": str(genetic_code.get("GCName", "")),
        "parent_taxid": str(record.get("ParentTaxId", "")),
        "kingdom": _kingdom(record),
        "lineage": _lineage(record),
        "match_score": score,
        "match_reason": reason,
        "source": source,
        # ranking detail only; the response model does not expose these
        "match_alignment": name_alignment(query, label),
        "match_corroboration": corroboration,
    }


def search(term: str, limit: int = 6) -> dict:
    """Search NCBI Taxonomy and return results in a defensible order."""

    term = (term or "").strip()

    if not term:
        return {"query": term, "count": 0, "results": [], "ambiguous": False}

    # Always ask. Capitalisation cannot tell a binomial from a common name a
    # phone auto-capitalised: "Sea horse" and "Panthera leo" are the same
    # shape, and guessing wrong silently loses every vernacular match.
    resolved = resolve_vernacular(term)

    taxids = []
    hint_by_taxid = {}

    for query, hint in build_queries(term, resolved):
        for taxid in _esearch(query):
            if taxid not in taxids:
                taxids.append(taxid)

            # First query to surface a taxid explains why it is here.
            if hint and taxid not in hint_by_taxid:
                hint_by_taxid[taxid] = hint

        # Enough precise matches; no need to keep widening.
        if len(taxids) >= MAX_CANDIDATES:
            break

    # Last resort only. A leading wildcard is what drags in Pandanus and
    # Seahorsevirus, so it runs only when nothing precise matched, and its
    # results still have to survive scoring below.
    if not taxids and "*" not in term:
        taxids = _esearch(f"{normalize(term)}*")

    if not taxids:
        return {"query": term, "count": 0, "results": [], "ambiguous": False}

    records = _efetch(taxids[:MAX_CANDIDATES])

    candidates = []

    for record in records:
        hint = hint_by_taxid.get(str(record.get("TaxId", "")), "")

        candidates.append(
            build_result(
                record,
                term,
                vernacular_hint=hint,
                source="gbif-resolved" if hint else "ncbi",
            )
        )

    ranked = rank_candidates(candidates, limit=limit)

    return {
        "query": term,
        "count": len(ranked),
        "results": ranked,
        "ambiguous": is_ambiguous(ranked),
    }


def get_species(taxid: str) -> dict:
    """One taxon by its NCBI TaxID."""

    records = _efetch([str(taxid)])

    if not records:
        raise LookupError(f"No taxonomy record for TaxID {taxid}")

    record = records[0]

    return build_result(record, str(record.get("ScientificName", "")))
