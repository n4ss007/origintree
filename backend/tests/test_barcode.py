"""The 8-base read window.

Offline. These pin down that the window is taken from real FASTA text and is
never padded, invented or silently short.
"""

from sequences import WINDOW_BASES, _first_window

FASTA = """>MZ049396.1 Ailuropoda melanoleuca cytochrome c oxidase subunit I (COX1) gene
CACTCTTTACCTACTATTCGGCGCATGAGCTGGAATAGTAGGCACTGCTCTGAGCCTCCT
CATTCGAGCCGAGCTGGGTCAGCCCGGCACTCTGCTAGGAGACGACCAGATCTACAATGT
"""


def test_the_window_is_exactly_eight_bases():
    bases, _ = _first_window(FASTA, WINDOW_BASES)

    assert len(bases) == 8
    assert bases == "CACTCTTT"


def test_the_header_line_is_not_read_as_sequence():
    bases, _ = _first_window(FASTA, WINDOW_BASES)

    # the description contains "cytochrome"; none of it may leak into the read
    assert set(bases) <= set("ACGT")


def test_ambiguity_codes_are_skipped_not_shown():
    """A base NCBI could not call is not a base. Skipping keeps the strip
    honest; padding or substituting would invent data."""

    fasta = ">x\nNNNNACGTACGTAC\n"

    bases, offset = _first_window(fasta, WINDOW_BASES)

    assert bases == "ACGTACGT"
    assert offset == 4


def test_a_short_record_returns_what_exists_rather_than_padding():
    fasta = ">x\nACGT\n"

    bases, _ = _first_window(fasta, WINDOW_BASES)

    assert bases == "ACGT"
    assert len(bases) < WINDOW_BASES  # caller marks this unavailable


def test_lowercase_sequence_is_read():
    fasta = ">x\nacgtacgtacgt\n"

    bases, _ = _first_window(fasta, WINDOW_BASES)

    assert bases == "ACGTACGT"


def test_blank_lines_and_wrapping_do_not_break_the_read():
    fasta = ">x\nACG\n\nTACG\nT\n"

    bases, _ = _first_window(fasta, WINDOW_BASES)

    assert bases == "ACGTACGT"


def test_an_empty_payload_yields_nothing():
    bases, offset = _first_window("", WINDOW_BASES)

    assert bases == ""
    assert offset == 0


def test_the_window_size_is_eight():
    """The strip is a fixed read window, not a tunable preview length."""

    assert WINDOW_BASES == 8
