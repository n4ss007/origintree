"""Molecular evidence: COX1 records held for a taxon.

COX1 is the mitochondrial gene used for animal DNA barcoding, which makes it
a good "does the genetic record agree?" companion to a lineage.

This is deliberately separate from the terminal version in ncbi_test.py.
`fetch_sequences()` there downloads full GenBank records and writes a FASTA
file, which is the right behaviour for a script and the wrong behaviour for a
web request. Here we ask for summaries only: no full sequences, no files.
"""

import rate_limit
from Bio import Entrez

import ncbi_test  # noqa: F401  — importing this configures Entrez.email and .tool

DEFAULT_GENE = "COX1"

# NCBI's `AND COX1[Gene]` also matches whole mitochondrial genomes and other
# multi-gene records, because those contain the gene. A 16 kb complete genome
# is not a barcode, so the record has to name the gene as well — the same
# confirmation the terminal script makes before accepting a sequence.
GENE_ALIASES = {
    "cox1": ("cox1", "coi", "co1", "cytochrome c oxidase subunit i", "cytochrome oxidase subunit i"),
}

# Fetch a wider pool than we show, so filtering and sorting happen across real
# candidates rather than across whatever arbitrary slice NCBI returned first.
POOL_MULTIPLIER = 5
MAX_POOL = 60

# A barcode is a gene-length read, not a genome. NCBI returns newest-first,
# and for well-sequenced organisms the newest records are complete
# mitochondrial genomes — for humans, every one of the first sixty is. Asking
# NCBI for barcode-length sequences skips them at the query level and finds
# the records this panel is actually about. Without it, human returns nothing.
MIN_BARCODE_LENGTH = 500
MAX_BARCODE_LENGTH = 2000


def _aliases(gene: str) -> tuple:
    key = gene.strip().lower()
    return GENE_ALIASES.get(key, (key,))


def _names_gene(title: str, gene: str) -> bool:
    """True when the record's own description names the gene we asked for."""

    lowered = title.lower()

    return any(alias in lowered for alias in _aliases(gene))


def _is_complete(title: str) -> bool:
    """GenBank titles say so when a coding sequence is only a fragment."""

    return "partial" not in title.lower()


def _empty(taxid, gene):
    return {
        "taxid": str(taxid),
        "gene": gene,
        "count": 0,
        "sequences": [],
        "available": False,
    }


def fetch_sequence_summaries(taxid: str, gene: str = DEFAULT_GENE, max_records: int = 8) -> dict:
    """Summaries of the gene records NCBI holds for this taxon and below.

    `txid...[Organism:exp]` expands to the whole subtree, so a genus returns
    records belonging to its species.

    Failures propagate rather than returning an empty result: "NCBI did not
    answer" and "NCBI holds nothing" are different facts, and reporting the
    first as the second tells the user something untrue about the record.
    """

    term = (
        f"txid{taxid}[Organism:exp] AND {gene}[Gene] "
        f"AND {MIN_BARCODE_LENGTH}:{MAX_BARCODE_LENGTH}[SLEN]"
    )
    pool = min(MAX_POOL, max(max_records, max_records * POOL_MULTIPLIER))

    rate_limit.wait()

    handle = Entrez.esearch(db="nuccore", term=term, retmax=pool)
    result = Entrez.read(handle)
    handle.close()

    ids = list(result.get("IdList", []))

    if not ids:
        return _empty(taxid, gene)

    rate_limit.wait()

    handle = Entrez.esummary(db="nuccore", id=",".join(ids))
    summaries = Entrez.read(handle)
    handle.close()

    sequences = []

    for summary in summaries:
        title = str(summary.get("Title", ""))

        if not _names_gene(title, gene):
            continue

        sequences.append(
            {
                # the nuccore UID, kept so the bases can be fetched later
                "uid": str(summary.get("Id", "")),
                "accession": str(summary.get("Caption", "") or summary.get("AccessionVersion", "")),
                "title": title,
                "length": int(summary.get("Length", 0) or 0),
                "organism": str(summary.get("Organism", "")),
                "complete": _is_complete(title),
            }
        )

    if not sequences:
        return _empty(taxid, gene)

    # Complete coding sequences are the more useful evidence, so lead with
    # them. Sorting the filtered pool, not a pre-truncated slice.
    sequences.sort(key=lambda s: (s["complete"], s["length"]), reverse=True)

    return {
        "taxid": str(taxid),
        "gene": gene,
        "count": len(sequences),
        "sequences": sequences[:max_records],
        "available": True,
    }


# The barcode strip shows exactly this many bases. It is a fixed read window,
# not a preview length to be tuned.
WINDOW_BASES = 8

_NUCLEOTIDES = set("ACGT")


def _first_window(fasta_text: str, size: int) -> tuple:
    """The first `size` unambiguous bases in a FASTA payload.

    GenBank records open with a header line, wrap the sequence across many
    lines, and use IUPAC ambiguity codes (N, R, Y…) where the read was not
    clean. Those are skipped rather than displayed, so the strip always shows
    `size` bases that were actually called — and the offset records how far
    into the record the window starts, so the number is not a fiction.
    """

    bases = []
    offset = None
    position = 0

    for line in fasta_text.splitlines():
        if line.startswith(">") or not line.strip():
            continue

        for char in line.strip().upper():
            if char in _NUCLEOTIDES:
                if offset is None:
                    offset = position
                bases.append(char)

                if len(bases) == size:
                    return "".join(bases), offset

            position += 1

    return "".join(bases), offset or 0


def fetch_fasta(uid: str) -> str:
    """The FASTA payload for one nuccore record, as GenBank returns it."""

    rate_limit.wait()

    handle = Entrez.efetch(db="nuccore", id=str(uid), rettype="fasta", retmode="text")
    text = handle.read()
    handle.close()

    return text


def read_sequence(fasta_text: str) -> str:
    """Every called base in a FASTA payload, header lines dropped.

    Ambiguity codes are kept here, unlike the display window: an aligner
    needs the sequence as GenBank actually recorded it.
    """

    return "".join(
        line.strip().upper()
        for line in fasta_text.splitlines()
        if line.strip() and not line.startswith(">")
    )


def fetch_barcode_window(taxid: str, gene: str = DEFAULT_GENE, size: int = WINDOW_BASES) -> dict:
    """Read a short window of real bases from this taxon's best COX1 record.

    These are the bases NCBI holds, fetched the same way the terminal script
    fetches them. Nothing here is generated: if NCBI has no confirmed record
    for the taxon, the window comes back empty and the interface shows
    nothing rather than inventing a sequence.
    """

    summaries = fetch_sequence_summaries(taxid, gene=gene, max_records=1)

    if not summaries["available"] or not summaries["sequences"]:
        return {
            "taxid": str(taxid),
            "gene": gene,
            "available": False,
            "bases": "",
            "accession": "",
            "organism": "",
            "offset": 0,
            "length": 0,
        }

    record = summaries["sequences"][0]

    fasta_text = fetch_fasta(record["uid"])

    bases, offset = _first_window(fasta_text, size)

    return {
        "taxid": str(taxid),
        "gene": gene,
        "available": len(bases) == size,
        "bases": bases,
        "accession": record["accession"],
        "organism": record["organism"],
        "offset": offset,
        "length": record["length"],
    }
