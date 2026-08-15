"""Gene-identity filtering for the molecular evidence panel.

Offline: these exercise the title checks, not NCBI.
"""

from sequences import _is_complete, _names_gene


def test_a_barcode_record_names_the_gene():
    title = (
        "Hippocampus hippocampus isolate S10 cytochrome c oxidase subunit I "
        "(COX1) gene, partial cds; mitochondrial"
    )

    assert _names_gene(title, "COX1") is True


def test_a_whole_mitochondrial_genome_is_not_a_barcode():
    """NCBI's `AND COX1[Gene]` matches complete genomes because they contain
    the gene. A 16 kb genome is not barcode evidence and must not be listed
    as one."""

    title = "Hippocampus hippocampus mitochondrion, complete genome"

    assert _names_gene(title, "COX1") is False


def test_the_common_abbreviations_are_accepted():
    assert _names_gene("... cytochrome oxidase subunit I (COI) gene ...", "COX1") is True
    assert _names_gene("Homo sapiens CO1 gene", "COX1") is True


def test_an_unrelated_gene_is_rejected():
    assert _names_gene("Panthera leo cytochrome b (CYTB) gene", "COX1") is False


def test_an_unknown_gene_falls_back_to_its_own_symbol():
    assert _names_gene("Panthera leo cytochrome b (CYTB) gene", "CYTB") is True
    assert _names_gene("Panthera leo COX1 gene", "CYTB") is False


def test_partial_coding_sequences_are_flagged():
    assert _is_complete("... (COX1) gene, partial cds; mitochondrial") is False
    assert _is_complete("... (COX1) gene, complete cds; mitochondrial") is True
