from Bio import Entrez, SeqIO
from pathlib import Path
import subprocess
import shutil
import time
import re


# ============================================================
# CONFIGURATION
# ============================================================

Entrez.email = "YOUR_EMAIL@example.com"

MARKERS = [
    "COX1",
    "CYTB",
    "ND1",
    "ND2",
    "RAG1",
    "RAG2",
    "IRBP",
    "BDNF"
]

MIN_LENGTH = 300
MIN_COVERAGE = 0.60
MAX_MARKERS = 5

SEQUENCE_DIR = Path("data/sequences")
ALIGNMENT_DIR = Path("data/alignments")
TREE_DIR = Path("data/trees")

for directory in [
    SEQUENCE_DIR,
    ALIGNMENT_DIR,
    TREE_DIR
]:
    directory.mkdir(
        parents=True,
        exist_ok=True
    )


# ============================================================
# NCBI
# ============================================================

def pause():
    time.sleep(0.34)


def taxonomy_search(name):

    pause()

    handle = Entrez.esearch(
        db="taxonomy",
        term=name,
        retmax=10
    )

    result = Entrez.read(handle)
    handle.close()

    return [
        str(x)
        for x in result["IdList"]
    ]


def taxonomy_record(taxid):

    pause()

    handle = Entrez.efetch(
        db="taxonomy",
        id=taxid,
        retmode="xml"
    )

    records = Entrez.read(handle)
    handle.close()

    return records[0]


def taxonomy_summary(taxid):

    record = taxonomy_record(taxid)

    lineage = []

    for node in record.get(
        "LineageEx",
        []
    ):

        lineage.append({
            "name":
                node["ScientificName"],

            "rank":
                node["Rank"],

            "taxid":
                str(node["TaxId"])
        })

    return {
        "taxid":
            str(taxid),

        "scientific_name":
            record["ScientificName"],

        "rank":
            record["Rank"],

        "lineage":
            lineage
    }


def find_rank(taxonomy, rank):

    for node in taxonomy["lineage"]:

        if node["rank"] == rank:
            return node["name"]

    return None


# ============================================================
# RELATED SPECIES
# ============================================================

def find_related_species(target):

    genus = find_rank(
        target,
        "genus"
    )

    if genus is None:
        return []

    print(
        f"\nSearching {genus} subtree..."
    )

    query = (
        f"{genus}[subtree] "
        f"AND species[rank]"
    )

    pause()

    handle = Entrez.esearch(
        db="taxonomy",
        term=query,
        retmax=100
    )

    result = Entrez.read(handle)
    handle.close()

    relatives = []

    for taxid in result["IdList"]:

        taxid = str(taxid)

        if taxid == target["taxid"]:
            continue

        try:
            tax = taxonomy_summary(
                taxid
            )

        except Exception:
            continue

        if tax["rank"] != "species":
            continue

        relatives.append(tax)

    return relatives


# ============================================================
# SEARCH MARKER
# ============================================================

def search_marker(
    taxid,
    marker
):

    query = (
        f"txid{taxid}[Organism:exp] "
        f"AND {marker}[Gene]"
    )

    pause()

    handle = Entrez.esearch(
        db="nuccore",
        term=query,
        retmax=50
    )

    result = Entrez.read(handle)
    handle.close()

    return [
        str(x)
        for x in result["IdList"]
    ]


# ============================================================
# DOWNLOAD GENBANK
# ============================================================

def download_records(ids):

    if not ids:
        return []

    pause()

    handle = Entrez.efetch(
        db="nuccore",
        id=ids,
        rettype="gb",
        retmode="text"
    )

    records = list(
        SeqIO.parse(
            handle,
            "genbank"
        )
    )

    handle.close()

    return records


# ============================================================
# EXTRACT MARKER
# ============================================================

def extract_marker(
    record,
    marker
):

    marker = marker.upper()

    for feature in record.features:

        if feature.type not in {
            "CDS",
            "gene"
        }:
            continue

        genes = []

        for key in [
            "gene",
            "gene_synonym"
        ]:

            genes.extend(
                feature.qualifiers.get(
                    key,
                    []
                )
            )

        for gene in genes:

            if gene.upper() == marker:

                return feature.extract(
                    record.seq
                )

        products = feature.qualifiers.get(
            "product",
            []
        )

        for product in products:

            p = product.upper()

            if marker == "COX1" and (
                "CYTOCHROME C OXIDASE SUBUNIT I"
                in p
            ):

                return feature.extract(
                    record.seq
                )

            if marker == "CYTB" and (
                "CYTOCHROME B"
                in p
            ):

                return feature.extract(
                    record.seq
                )

            if marker == "RAG1" and (
                "RECOMBINATION ACTIVATING GENE 1"
                in p
            ):

                return feature.extract(
                    record.seq
                )

            if marker == "RAG2" and (
                "RECOMBINATION ACTIVATING GENE 2"
                in p
            ):

                return feature.extract(
                    record.seq
                )

    return None


# ============================================================
# QC
# ============================================================

def good_sequence(sequence):

    sequence = str(
        sequence
    ).upper()

    if len(sequence) < MIN_LENGTH:
        return False

    if "N" in sequence:
        return False

    if set(sequence) - set("ACGT"):
        return False

    return True


# ============================================================
# RETRIEVE MARKER FOR SPECIES
# ============================================================

def retrieve_marker(
    taxonomy,
    marker
):

    species = taxonomy[
        "scientific_name"
    ]

    ids = search_marker(
        taxonomy["taxid"],
        marker
    )

    records = download_records(
        ids
    )

    candidates = []

    for record in records:

        organism = record.annotations.get(
            "organism",
            ""
        )

        # Exact species only.
        if organism != species:
            continue

        sequence = extract_marker(
            record,
            marker
        )

        if sequence is None:
            continue

        sequence = str(
            sequence
        ).upper()

        if not good_sequence(
            sequence
        ):
            continue

        candidates.append({
            "accession":
                record.id,

            "organism":
                organism,

            "sequence":
                sequence,

            "length":
                len(sequence)
        })

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda x: x["length"]
    )


# ============================================================
# EVALUATE MARKERS
# ============================================================

def evaluate_markers(
    taxa
):

    results = {}

    print()
    print(
        "=========================================="
    )
    print(
        "MARKER EVALUATION"
    )
    print(
        "=========================================="
    )

    for marker in MARKERS:

        print()
        print(
            f"Testing {marker}..."
        )

        sequences = {}

        for taxon in taxa:

            result = retrieve_marker(
                taxon,
                marker
            )

            if result:

                sequences[
                    taxon["scientific_name"]
                ] = result

        coverage = (
            len(sequences)
            /
            len(taxa)
        )

        lengths = [
            x["length"]
            for x in sequences.values()
        ]

        median_length = (
            sorted(lengths)[
                len(lengths) // 2
            ]
            if lengths
            else 0
        )

        results[marker] = {
            "coverage":
                coverage,

            "count":
                len(sequences),

            "median_length":
                median_length,

            "sequences":
                sequences
        }

        print(
            f"  Taxa: {len(sequences)}/{len(taxa)}"
        )

        print(
            f"  Coverage: "
            f"{coverage * 100:.1f}%"
        )

        print(
            f"  Median length: "
            f"{median_length}"
        )

    return results


# ============================================================
# SELECT MARKERS
# ============================================================

def select_markers(
    results
):

    ranked = []

    for marker, result in results.items():

        if (
            result["coverage"]
            >= MIN_COVERAGE
        ):

            score = (
                result["coverage"] * 100
                +
                min(
                    result["median_length"],
                    2000
                ) / 100
            )

            ranked.append(
                (
                    score,
                    marker
                )
            )

    ranked.sort(
        reverse=True
    )

    return [
        marker
        for score, marker
        in ranked[:MAX_MARKERS]
    ]


# ============================================================
# SAVE FASTA
# ============================================================

def save_fastas(
    selected,
    results
):

    files = {}

    for marker in selected:

        filename = (
            SEQUENCE_DIR
            /
            f"{marker}.fasta"
        )

        with open(
            filename,
            "w"
        ) as output:

            for species, result in (
                results[
                    marker
                ]["sequences"].items()
            ):

                safe = re.sub(
                    r"[^A-Za-z0-9_.-]",
                    "_",
                    species
                )

                output.write(
                    f">{safe}|"
                    f"{result['accession']}\n"
                )

                output.write(
                    result["sequence"]
                    + "\n"
                )

        files[marker] = filename

        print(
            f"Saved {marker}: {filename}"
        )

    return files


# ============================================================
# MAFFT
# ============================================================

def run_mafft(
    marker,
    fasta
):

    mafft = shutil.which(
        "mafft"
    )

    if mafft is None:

        raise RuntimeError(
            "MAFFT not found."
        )

    output = (
        ALIGNMENT_DIR
        /
        f"{marker}_alignment.fasta"
    )

    print(
        f"\nAligning {marker}..."
    )

    with open(
        output,
        "w"
    ) as handle:

        process = subprocess.run(
            [
                mafft,
                "--auto",
                str(fasta)
            ],
            stdout=handle,
            stderr=subprocess.PIPE,
            text=True
        )

    if process.returncode != 0:

        print(process.stderr)

        raise RuntimeError(
            f"MAFFT failed for {marker}"
        )

    print(
        "Alignment:",
        output
    )

    return output


# ============================================================
# CONCATENATE ALIGNMENTS
# ============================================================

def concatenate(
    selected,
    alignments
):

    data = {}
    lengths = {}

    for marker in selected:

        records = list(
            SeqIO.parse(
                alignments[marker],
                "fasta"
            )
        )

        if not records:
            continue

        lengths[marker] = len(
            records[0].seq
        )

        for record in records:

            species = (
                record.id.split("|")[0]
            )

            if species not in data:
                data[species] = {}

            data[species][marker] = (
                str(record.seq)
            )

    species_list = sorted(
        data.keys()
    )

    combined = (
        ALIGNMENT_DIR
        /
        "multimarker_concatenated.fasta"
    )

    with open(
        combined,
        "w"
    ) as output:

        for species in species_list:

            sequence = ""

            for marker in selected:

                length = lengths[
                    marker
                ]

                sequence += data[
                    species
                ].get(
                    marker,
                    "?" * length
                )

            output.write(
                f">{species}\n"
            )

            output.write(
                sequence
                + "\n"
            )

    return combined, lengths


# ============================================================
# IQ-TREE
# ============================================================

def find_iqtree():

    for name in [
        "iqtree3",
        "iqtree2",
        "iqtree"
    ]:

        path = shutil.which(
            name
        )

        if path:
            return path

    return None


def run_iqtree(
    alignment,
    lengths,
    selected
):

    iqtree = find_iqtree()

    if iqtree is None:

        raise RuntimeError(
            "IQ-TREE not found."
        )

    partition = (
        TREE_DIR
        /
        "multimarker_partitions.nex"
    )

    start = 1

    with open(
        partition,
        "w"
    ) as output:

        output.write(
            "#nexus\n\n"
        )

        output.write(
            "begin sets;\n"
        )

        for marker in selected:

            end = (
                start
                +
                lengths[marker]
                -
                1
            )

            output.write(
                f"    charset "
                f"{marker} = "
                f"{start}-{end};\n"
            )

            start = end + 1

        output.write(
            "end;\n"
        )

    prefix = (
        TREE_DIR
        /
        "multimarker_ML"
    )

    command = [

        iqtree,

        "-redo",

        "-s",
        str(alignment),

        "-p",
        str(partition),

        "-m",
        "MFP+MERGE",

        "-bb",
        "1000",

        "-alrt",
        "1000",

        "-pre",
        str(prefix)
    ]

    print()
    print(
        "=========================================="
    )
    print(
        "RUNNING IQ-TREE"
    )
    print(
        "=========================================="
    )

    process = subprocess.run(
        command
    )

    if process.returncode != 0:

        raise RuntimeError(
            "IQ-TREE failed."
        )

    tree = Path(
        str(prefix)
        + ".treefile"
    )

    print(
        "\nTree saved:",
        tree
    )

    return tree


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "=========================================="
    )
    print(
        "       MULTI-MARKER EVOLUTION PIPELINE"
    )
    print(
        "=========================================="
    )

    common_name = input(
        "\nEnter an animal: "
    ).strip()

    if not common_name:
        return

    # --------------------------------------------------------
    # TARGET
    # --------------------------------------------------------

    taxids = taxonomy_search(
        common_name
    )

    if not taxids:

        print(
            "No taxonomy match."
        )

        return

    target = None

    for taxid in taxids:

        tax = taxonomy_summary(
            taxid
        )

        if tax["rank"] == "species":

            target = tax
            break

    if target is None:

        print(
            "No species-level match."
        )

        return

    print()
    print(
        "Target:",
        target["scientific_name"]
    )

    print(
        "TaxID:",
        target["taxid"]
    )

    # --------------------------------------------------------
    # RELATIVES
    # --------------------------------------------------------

    relatives = find_related_species(
        target
    )

    taxa = [
        target
    ] + relatives[:8]

    # Remove duplicates.
    unique = {}

    for taxon in taxa:

        unique[
            taxon["scientific_name"]
        ] = taxon

    taxa = list(
        unique.values()
    )

    print()
    print(
        "Taxa selected:"
    )

    for taxon in taxa:

        print(
            "-",
            taxon["scientific_name"]
        )

    # --------------------------------------------------------
    # MARKERS
    # --------------------------------------------------------

    results = evaluate_markers(
        taxa
    )

    selected = select_markers(
        results
    )

    print()
    print(
        "=========================================="
    )
    print(
        "SELECTED MARKERS"
    )
    print(
        "=========================================="
    )

    if not selected:

        print(
            "No markers passed coverage threshold."
        )

        return

    for marker in selected:

        coverage = (
            results[marker]["coverage"]
            * 100
        )

        print(
            f"{marker}: "
            f"{coverage:.1f}% coverage"
        )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    fastas = save_fastas(
        selected,
        results
    )

    # --------------------------------------------------------
    # ALIGN
    # --------------------------------------------------------

    alignments = {}

    for marker in selected:

        alignments[marker] = (
            run_mafft(
                marker,
                fastas[marker]
            )
        )

    # --------------------------------------------------------
    # CONCATENATE
    # --------------------------------------------------------

    combined, lengths = concatenate(
        selected,
        alignments
    )

    print()
    print(
        "Combined alignment:",
        combined
    )

    # --------------------------------------------------------
    # TREE
    # --------------------------------------------------------

    tree = run_iqtree(
        combined,
        lengths,
        selected
    )

    print()
    print(
        "=========================================="
    )
    print(
        "MULTI-MARKER ANALYSIS COMPLETE"
    )
    print(
        "=========================================="
    )

    print()
    print(
        "Selected markers:",
        ", ".join(selected)
    )

    print(
        "Alignment:",
        combined
    )

    print(
        "Tree:",
        tree
    )

    print()
    print(
        "Next stage:"
    )

    print(
        "Fossil calibrations → BEAUti → BEAST2"
    )


if __name__ == "__main__":
    main()
