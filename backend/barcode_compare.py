"""How similar two organisms' DNA barcodes actually are.

The comparison next door answers this from classification: two organisms
share ranks down to some point, then part. This answers it from the
molecule — align the COX1 barcode of each and count how many bases agree.

COX1 is the standard animal barcoding gene precisely because it varies
enough between species to tell them apart while staying similar enough
within one to be recognisable, so the number means something to a student
learning barcoding.

Identity is matching columns over aligned length, as in the project's own
compare_sequences.py. The alignment itself is *local*, not global: that
script compares records of one species that cover the same stretch of the
gene, whereas two organisms picked at random are often sequenced over
different, partly overlapping stretches. A global alignment of two such
records reports the mismatch in coverage rather than the difference between
the organisms — it once scored a lion against a snow leopard lower than a
lion against an octopus. A local alignment compares the region they share,
which is the meaningful question.

Nothing here is estimated. If NCBI holds no confirmed COX1 record for one
of the organisms, the comparison reports that it is unavailable rather than
returning a number.
"""

from Bio.Align import PairwiseAligner
from Bio.Seq import Seq

from sequences import DEFAULT_GENE, fetch_fasta, fetch_sequence_summaries, read_sequence

# Full COX1 records run to whole mitochondrial genomes in some entries. An
# alignment of two 16 kb sequences is slow and tells a student nothing about
# barcoding, so each sequence is capped at a generous multiple of the ~658 bp
# barcode region.
MAX_BASES = 2000

# Below this many aligned bases the identity figure is not worth showing:
# a few dozen columns of overlap can read anywhere from 50% to 90% on the
# same pair of organisms. Roughly a third of the COX1 barcode region.
MIN_OVERLAP = 200

# Defaults score a match 1 and everything else 0, so gaps are free and the
# aligner will happily pull sequences apart to collect stray matches. Real
# penalties are what make the alignment mean anything.
_ALIGNER = PairwiseAligner()
_ALIGNER.mode = "local"
_ALIGNER.match_score = 1
_ALIGNER.mismatch_score = -1
_ALIGNER.open_gap_score = -2
_ALIGNER.extend_gap_score = -0.5


def _unavailable(reason: str) -> dict:
    return {
        "available": False,
        "reason": reason,
        "gene": DEFAULT_GENE,
        "identity": None,
        "matches": 0,
        "differences": 0,
        "aligned_length": 0,
        "a": None,
        "b": None,
    }


def _best_record(taxid: str, gene: str):
    """The strongest confirmed record for a taxon, with its bases."""

    summaries = fetch_sequence_summaries(taxid, gene=gene, max_records=1)

    if not summaries["available"] or not summaries["sequences"]:
        return None

    record = summaries["sequences"][0]
    sequence = read_sequence(fetch_fasta(record["uid"]))

    if not sequence:
        return None

    return {
        "accession": record["accession"],
        "organism": record["organism"],
        "length": record["length"],
        "sequence": sequence[:MAX_BASES],
    }


def _identity(left: str, right: str) -> tuple:
    """(identity percent, matching columns, aligned length) for one orientation."""

    alignment = _ALIGNER.align(left, right)[0]

    a_aligned = alignment[0]
    b_aligned = alignment[1]
    length = len(a_aligned)

    if not length:
        return (0.0, 0, 0)

    matches = sum(1 for x, y in zip(a_aligned, b_aligned) if x == y)

    return ((matches / length) * 100, matches, length)


def compare_barcodes(taxid_a: str, taxid_b: str, gene: str = DEFAULT_GENE) -> dict:
    """Align two organisms' barcodes and report how much they agree.

    `identity` is the percentage of aligned columns where both sequences
    carry the same base — the same figure compare_sequences.py prints.
    """

    if str(taxid_a) == str(taxid_b):
        return _unavailable("Those are the same organism.")

    record_a = _best_record(taxid_a, gene)
    record_b = _best_record(taxid_b, gene)

    if record_a is None or record_b is None:
        missing = "both organisms" if record_a is None and record_b is None else "one of them"
        return _unavailable(f"NCBI holds no confirmed {gene} record for {missing}.")

    # GenBank stores records in whichever orientation the submitter used, so
    # the same gene can appear reverse-complemented. Both are tried and the
    # better alignment wins; otherwise a strand difference reads as a species
    # difference.
    forward = _identity(record_a["sequence"], record_b["sequence"])
    reverse = _identity(
        record_a["sequence"], str(Seq(record_b["sequence"]).reverse_complement())
    )

    best = forward if forward[0] >= reverse[0] else reverse
    matches, aligned_length = best[1], best[2]

    if not aligned_length:
        return _unavailable("Those sequences could not be aligned.")

    if aligned_length < MIN_OVERLAP:
        return _unavailable(
            f"The available records overlap by only {aligned_length} bases — "
            "too little to compare reliably."
        )

    identity = best[0]

    return {
        "available": True,
        "reason": "",
        "gene": gene,
        "identity": round(identity, 2),
        "matches": matches,
        "differences": aligned_length - matches,
        "aligned_length": aligned_length,
        "a": {k: record_a[k] for k in ("accession", "organism", "length")},
        "b": {k: record_b[k] for k in ("accession", "organism", "length")},
    }
