"""Checking what callers send before it reaches NCBI.

Search terms and identifiers are built into Entrez query strings, and Entrez
has a query language: brackets delimit fields, `AND`/`OR` combine clauses.
An identifier taken on trust and pasted into that string lets a caller write
the query themselves —

    /api/species/9606[Organism:exp] AND COX1[Gene] OR txid9606/sequences

— which returned human records from an endpoint that was never asked about
humans. Nothing is leaked from this server by that, but the query runs
against NCBI under our address, and NCBI blocks addresses that abuse the
service. So identifiers are checked against what they are actually allowed
to look like, rather than being escaped.
"""

import re

# NCBI taxonomy identifiers are plain integers. Anything else is not a taxid,
# so there is no reason to pass it on and every reason not to.
TAXID = re.compile(r"^[0-9]{1,12}$")

# Gene symbols are short and alphanumeric: COX1, ND2, RAG1, MT-CO1.
GENE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,23}$")

# Longest search term worth forwarding. Real organism names are far shorter,
# and an unbounded string is just a way to make NCBI do unnecessary work.
MAX_TERM_LENGTH = 120

# Characters that carry meaning inside an Entrez query. Stripped from free
# text, which is a phrase to search for and never syntax.
_QUERY_SYNTAX = re.compile(r"[\[\]()\"\\]")


# Control characters, including the NUL byte, have no place in a search term
# and only serve to confuse whatever parser eventually sees them.
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class InvalidInput(ValueError):
    """A caller sent something that is not the kind of value it claims to be."""


def taxid(value: str) -> str:
    """A validated NCBI taxonomy identifier."""

    candidate = (value or "").strip()

    if not TAXID.match(candidate):
        raise InvalidInput("A TaxID is a number, for example 9689.")

    return candidate


def gene(value: str) -> str:
    """A validated gene symbol."""

    candidate = (value or "").strip()

    if not GENE.match(candidate):
        raise InvalidInput("A gene symbol looks like COX1 or ND2.")

    return candidate


def search_term(value: str) -> str:
    """Free text, with Entrez syntax removed and length bounded.

    Unlike an identifier this cannot be pattern-matched — people search for
    hyphenated and apostrophised names — so the query-language characters
    are removed and the rest is passed through.
    """

    candidate = _CONTROL.sub("", value or "")
    candidate = _QUERY_SYNTAX.sub(" ", candidate).strip()
    candidate = re.sub(r"\s+", " ", candidate)

    if not candidate:
        raise InvalidInput("Enter an organism to search for.")

    return candidate[:MAX_TERM_LENGTH]


def taxid_or_term(value: str) -> str:
    """Either identifier, for endpoints that accept a name or a TaxID."""

    candidate = (value or "").strip()

    if TAXID.match(candidate):
        return candidate

    return search_term(candidate)
