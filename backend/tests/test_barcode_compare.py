"""Barcode comparison: the alignment method, not the network.

The identity figure is only meaningful if the alignment is. These pin down
the three things that made it meaningless before: global alignment across
records covering different stretches of the gene, free gaps, and records
stored on opposite strands.
"""

import barcode_compare
from barcode_compare import MIN_OVERLAP, _identity, compare_barcodes

# A real 120-base stretch of COX1 from Panthera leo (PQ898395).
LION = (
    "AATAATTGGAGCCCCCGATATAGCATTCCCTCGAATGAATAACATAAGCTTCTGACTCCTACCCCCATCT"
    "TTCCTACTACTAATAGCATCCTCCATAGTAGAAGCCGGAGCAGGAACTGGATGAAC"
)


def _mutate(sequence: str, every: int) -> str:
    """Change one base in every `every` — a crude stand-in for divergence."""

    swap = {"A": "G", "G": "A", "C": "T", "T": "C"}
    return "".join(
        swap[base] if index % every == 0 else base for index, base in enumerate(sequence)
    )


def _reverse_complement(sequence: str) -> str:
    pairs = {"A": "T", "T": "A", "C": "G", "G": "C"}
    return "".join(pairs[base] for base in reversed(sequence))


# ---- the identity calculation ------------------------------------------


def test_identical_sequences_score_100():
    identity, matches, length = _identity(LION, LION)

    assert identity == 100.0
    assert matches == length == len(LION)


def test_divergence_lowers_identity_proportionally():
    near = _identity(LION, _mutate(LION, 20))[0]
    far = _identity(LION, _mutate(LION, 5))[0]

    assert near > far
    assert 80 < near < 100


def test_a_short_fragment_aligns_to_its_own_region():
    """A partial record must match the part of the gene it covers, not be
    penalised for the part it does not."""

    fragment = LION[30:90]

    identity, _, length = _identity(LION, fragment)

    assert identity == 100.0
    # local alignment reports the overlap, not the longer sequence
    assert length == len(fragment)


def test_gaps_are_penalised():
    """With free gaps the aligner pulls sequences apart to collect stray
    matches, which is what made a lion look less like a snow leopard than
    like an octopus."""

    assert barcode_compare._ALIGNER.open_gap_score < 0
    assert barcode_compare._ALIGNER.extend_gap_score < 0
    assert barcode_compare._ALIGNER.mismatch_score < 0


def test_alignment_is_local():
    assert barcode_compare._ALIGNER.mode == "local"


# ---- strand ------------------------------------------------------------


def test_a_reverse_complemented_record_is_recognised(monkeypatch):
    """GenBank stores whichever orientation the submitter used. A strand
    difference must not read as a species difference."""

    forward = {"accession": "A1", "organism": "a", "length": len(LION), "sequence": LION}
    flipped = {
        "accession": "B1",
        "organism": "b",
        "length": len(LION),
        "sequence": _reverse_complement(LION),
    }

    monkeypatch.setattr(
        barcode_compare,
        "_best_record",
        lambda taxid, gene: forward if taxid == "1" else flipped,
    )
    # this fixture is shorter than a real barcode; the overlap floor has its
    # own test, and applying it here would mask what is being checked
    monkeypatch.setattr(barcode_compare, "MIN_OVERLAP", 50)

    result = compare_barcodes("1", "2")

    assert result["available"] is True
    assert result["identity"] == 100.0


# ---- guards ------------------------------------------------------------


def test_too_little_overlap_is_refused_rather_than_reported(monkeypatch):
    short = LION[:40]

    monkeypatch.setattr(
        barcode_compare,
        "_best_record",
        lambda taxid, gene: {
            "accession": taxid,
            "organism": "",
            "length": 40,
            "sequence": short if taxid == "1" else _mutate(short, 7),
        },
    )

    result = compare_barcodes("1", "2")

    assert result["available"] is False
    assert result["identity"] is None
    assert "overlap" in result["reason"].lower()


def test_the_same_organism_is_not_compared_with_itself():
    result = compare_barcodes("9689", "9689")

    assert result["available"] is False
    assert result["identity"] is None


def test_a_missing_record_yields_no_number(monkeypatch):
    monkeypatch.setattr(barcode_compare, "_best_record", lambda taxid, gene: None)

    result = compare_barcodes("1", "2")

    assert result["available"] is False
    assert result["identity"] is None
    assert result["matches"] == 0


def test_the_overlap_floor_is_a_meaningful_fraction_of_a_barcode():
    """The COX1 barcode region is about 658 bases."""

    assert 100 <= MIN_OVERLAP <= 400
