"""Input validation.

The case that motivated this: `taxid` was pasted straight into an Entrez
query, so a caller could write the query themselves and have it run against
NCBI under this server's address.
"""

import pytest

import validation
from validation import InvalidInput, gene, search_term, taxid, taxid_or_term


# ---- taxid --------------------------------------------------------------


def test_a_real_taxid_passes():
    assert taxid("9689") == "9689"
    assert taxid("  9606 ") == "9606"


@pytest.mark.parametrize(
    "payload",
    [
        # the exploit that returned Homo sapiens records from an endpoint
        # that was never asked about humans
        "9606[Organism:exp] AND COX1[Gene] AND 500:2000[SLEN] OR txid9606",
        "9689 OR txid9606",
        "9689[Organism:exp]",
        "../../etc/passwd",
        "9689'",
        '9689"',
        "-1",
        "9689.0",
        "",
        "   ",
        "9" * 13,
    ],
)
def test_anything_that_is_not_a_number_is_refused(payload):
    with pytest.raises(InvalidInput):
        taxid(payload)


# ---- gene ---------------------------------------------------------------


def test_real_gene_symbols_pass():
    for symbol in ("COX1", "ND2", "RAG1", "MT-CO1", "co1"):
        assert gene(symbol) == symbol


@pytest.mark.parametrize(
    "payload",
    ["COX1] OR x[", "COX1[Gene] OR txid9606[Organism:exp", "", "COX1 OR ND2", "a" * 30],
)
def test_gene_symbols_carrying_query_syntax_are_refused(payload):
    with pytest.raises(InvalidInput):
        gene(payload)


# ---- free text ----------------------------------------------------------


def test_ordinary_names_survive_unchanged():
    assert search_term("giant panda") == "giant panda"
    assert search_term("Panthera leo") == "Panthera leo"


def test_hyphens_and_apostrophes_are_kept():
    """Real organism names contain them, so a pattern match is not an option."""

    assert search_term("Przewalski's horse") == "Przewalski's horse"
    assert search_term("sabre-toothed cat") == "sabre-toothed cat"


def test_query_syntax_is_stripped_from_free_text():
    cleaned = search_term('lion[Organism] OR (human)"')

    for character in "[]()\"\\":
        assert character not in cleaned


def test_a_term_is_bounded():
    assert len(search_term("a" * 500)) == validation.MAX_TERM_LENGTH


def test_an_empty_term_is_refused():
    for payload in ("", "   ", "[]"):
        with pytest.raises(InvalidInput):
            search_term(payload)


# ---- either -------------------------------------------------------------


def test_taxid_or_term_accepts_both():
    assert taxid_or_term("9689") == "9689"
    assert taxid_or_term("snow leopard") == "snow leopard"


def test_taxid_or_term_still_strips_syntax_from_names():
    assert "[" not in taxid_or_term("lion[Organism:exp]")


def test_control_characters_are_removed():
    """A NUL byte reached the query before this."""

    assert "\x00" not in search_term("lion\x00")
    assert search_term("li\ton") == "lion"
