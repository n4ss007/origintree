import os

from Bio import Entrez, SeqIO
from pathlib import Path
import subprocess
import shutil
import re
import json
import time



# CONFIGURATION



Entrez.email = os.environ.get("NCBI_EMAIL", "YOUR_EMAIL@example.com")

Entrez.tool = "EvolutionProject"

GENE = "COX1"

MIN_COX1_LENGTH = 1400
MAX_NCBI_RECORDS = 50
MAX_RELATED_SPECIES = 8

SEQUENCE_DIR = Path("data/sequences")
ALIGNMENT_DIR = Path("data/alignments")
TREE_DIR = Path("data/trees")
RESULT_DIR = Path("results")

for directory in [
    SEQUENCE_DIR,
    ALIGNMENT_DIR,
    TREE_DIR,
    RESULT_DIR
]:
    directory.mkdir(
        parents=True,
        exist_ok=True
    )



def ncbi_request_pause():
    time.sleep(0.34)



# 1. SEARCH NCBI TAXONOMY

def search_taxonomy(name, max_results=10):

    ncbi_request_pause()

    handle = Entrez.esearch(
        db="taxonomy",
        term=name,
        retmax=max_results
    )

    result = Entrez.read(handle)
    handle.close()

    return [
        str(taxid)
        for taxid in result["IdList"]
    ]



# 2. GET TAXONOMY RECORD


def get_taxonomy_record(taxid):

    ncbi_request_pause()

    handle = Entrez.efetch(
        db="taxonomy",
        id=str(taxid),
        retmode="xml"
    )

    records = Entrez.read(handle)
    handle.close()

    if not records:
        raise RuntimeError(
            f"No taxonomy record for TaxID {taxid}"
        )

    return records[0]



# 3. SUMMARIZE TAXONOMY


def summarize_taxonomy(taxid):

    record = get_taxonomy_record(taxid)

    lineage = []

    for node in record.get("LineageEx", []):

        lineage.append({
            "taxid": str(node["TaxId"]),
            "name": node["ScientificName"],
            "rank": node["Rank"]
        })

    return {
        "taxid": str(taxid),
        "scientific_name": record["ScientificName"],
        "rank": record["Rank"],
        "lineage": lineage
        }


# 4. FIND GENUS

def find_genus(taxonomy):

    for node in taxonomy["lineage"]:

        if node["rank"] == "genus":
            return node["name"]

    return None

#5 FIND RELATED SPECIES

def find_related_species(target_taxonomy):

    target_taxid = target_taxonomy["taxid"]
    target_name = target_taxonomy["scientific_name"]

    genus = find_genus(target_taxonomy)

    if genus is None:
        print("Could not determine genus.")
        return []

    print()
    print(
        f"Searching NCBI for species related "
        f"to {target_name}..."
    )

    # NCBI Taxonomy supports [subtree].
    # This retrieves taxa below the genus node.
    query = (
        f"{genus}[subtree] "
        f"AND species[rank]"
    )

    ncbi_request_pause()

    handle = Entrez.esearch(
        db="taxonomy",
        term=query,
        retmax=100
    )

    result = Entrez.read(handle)
    handle.close()

    candidate_ids = [
        str(x)
        for x in result["IdList"]
    ]

    print(
        "Candidate taxonomy records:",
        len(candidate_ids)
    )

    candidates = []

    for taxid in candidate_ids:

        if taxid == target_taxid:
            continue

        try:

            taxonomy = summarize_taxonomy(
                taxid
            )

        except Exception as error:

            print(
                f"Could not retrieve "
                f"TaxID {taxid}: {error}"
            )

            continue

        if taxonomy["rank"] != "species":
            continue

        if (
            taxonomy["scientific_name"]
            == target_name
        ):
            continue

        candidates.append(
            taxonomy
        )

    print()
    print("Candidate related species:")

    for candidate in candidates:

        print(
            "-",
            candidate["scientific_name"],
            "| TaxID:",
            candidate["taxid"]
        )

    return candidates



# 5. FIND RELATED SPECIES


    print()
    print(
        "[5/9] Retrieving and filtering COX1..."
    )

    sequence_files = []
    representatives = []
    successful_taxa = []

    for taxonomy in taxa:

        print()
        print(
            "Testing taxon:",
            taxonomy["scientific_name"]
        )

        candidates = get_cox1_candidates(
            taxonomy
        )

        representative = select_representative(
            candidates
        )

        if representative is None:

            print(
                "No usable COX1 for",
                taxonomy["scientific_name"]
            )

            continue

        print()
        print("REPRESENTATIVE")
        print(
            "Accession:",
            representative["accession"]
        )
        print(
            "Organism:",
            representative["organism"]
        )
        print(
            "COX1 length:",
            representative["length"],
            "bp"
        )

        fasta_file = save_species_sequence(
            representative
        )

        print(
            "Saved:",
            fasta_file
        )

        sequence_files.append(
            str(fasta_file)
        )

        representatives.append(
            representative
        )

        successful_taxa.append(
            taxonomy
        )

    print()
    print(
        "Species with usable sequences:",
        len(successful_taxa)
    )

    print()
    print("Usable species:")

    for taxonomy in successful_taxa:

        print(
            "-",
            taxonomy["scientific_name"]
        )

    if len(successful_taxa) < 3:

        print()
        print(
            "Not enough usable taxa."
        )

        print(
            "We need at least 3 species "
            "for the initial tree."
        )

        return



# 6. SEARCH NCBI NUCLEOTIDE FOR COX1

def search_gene_records(
    taxid,
    gene=GENE,
    max_results=MAX_NCBI_RECORDS
):

    query = (
        f"txid{taxid}[Organism:exp] "
        f"AND {gene}[Gene]"
    )

    ncbi_request_pause()

    handle = Entrez.esearch(
        db="nuccore",
        term=query,
        retmax=max_results
    )

    result = Entrez.read(handle)
    handle.close()

    return [
        str(uid)
        for uid in result["IdList"]
    ]


# 7. DOWNLOAD GENBANK RECORDS


def download_genbank_records(record_ids):

    if not record_ids:
        return []

    ncbi_request_pause()

    handle = Entrez.efetch(
        db="nuccore",
        id=record_ids,
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



# 8. EXTRACT COX1


def extract_cox1(record):

    for feature in record.features:

        if feature.type not in {
            "CDS",
            "gene"
        }:
            continue

        # Check gene names
        gene_names = []

        for qualifier_name in [
            "gene",
            "gene_synonym"
        ]:

            gene_names.extend(
                feature.qualifiers.get(
                    qualifier_name,
                    []
                )
            )

        for gene_name in gene_names:

            normalized = (
                gene_name.strip().upper()
            )

            if normalized in {
                "COX1",
                "COI",
                "COX-I"
            }:

                return feature.extract(
                    record.seq
                )

        # Check product annotation
        products = feature.qualifiers.get(
            "product",
            []
        )

        for product in products:

            if (
                "cytochrome c oxidase "
                "subunit i"
                in product.lower()
            ):

                return feature.extract(
                    record.seq
                )

    return None



# 9. SEQUENCE QUALITY

def check_sequence_quality(sequence):

    sequence = str(sequence).upper()

    if len(sequence) < MIN_COX1_LENGTH:

        return (
            False,
            "sequence is too short"
        )

    if "N" in sequence:

        return (
            False,
            "ambiguous N bases"
        )

    invalid = set(sequence) - set("ACGT")

    if invalid:

        return (
            False,
            f"invalid bases: {invalid}"
        )

    return (
        True,
        "passed"
    )

# 10. GET COX1 CANDIDATES FOR ONE SPECIES


def get_cox1_candidates(taxonomy):

    taxid = taxonomy["taxid"]

    species_name = taxonomy["scientific_name"]

    print()
    print("==========================================")
    print("PROCESSING:", species_name)
    print("TaxID:", taxid)
    print("==========================================")

    record_ids = search_gene_records(taxid)

    print(
        "Candidate NCBI records:",
        len(record_ids)
    )

    if not record_ids:
        return []

    records = download_genbank_records(
        record_ids
    )

    candidates = []

    for record in records:

        organism = record.annotations.get(
            "organism",
            ""
        )

        # Exact species match
        if organism != species_name:

            print(
                f"REJECTED {record.id}: "
                f"organism = {organism}"
            )

            continue

        sequence = extract_cox1(record)

        if sequence is None:

            print(
                f"REJECTED {record.id}: "
                "COX1 feature not found"
            )

            continue

        passed, reason = check_sequence_quality(
            sequence
        )

        if not passed:

            print(
                f"REJECTED {record.id}: "
                f"{reason}"
            )

            continue

        candidate = {
            "accession": record.id,
            "organism": organism,
            "description": record.description,
            "sequence": str(sequence).upper(),
            "length": len(sequence)
        }

        candidates.append(candidate)

        print(
            f"ACCEPTED {record.id}: "
            f"COX1 = {len(sequence)} bp"
        )

    return candidates



# 11. SELECT REPRESENTATIVE


def select_representative(candidates):

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda x: x["length"]
    )


# 12. SAFE FILE NAME

def safe_filename(name):

    return re.sub(
        r"[^A-Za-z0-9_.-]",
        "_",
        name
    )



# 13. SAVE SPECIES COX1 FASTA


def save_species_sequence(representative):

    species = representative["organism"]

    filename = (
        SEQUENCE_DIR
        / f"{safe_filename(species)}_{GENE}.fasta"
    )

    with open(
        filename,
        "w"
    ) as output:

        output.write(
            f">{representative['accession']}|"
            f"{species}\n"
        )

        output.write(
            representative["sequence"]
            + "\n"
        )

    return filename


# 14. COMBINE SPECIES FASTA FILES


def combine_fastas(files):

    combined = (
        SEQUENCE_DIR
        / f"combined_{GENE}.fasta"
    )

    with open(
        combined,
        "w"
    ) as output:

        for filename in files:

            with open(
                filename,
                "r"
            ) as input_file:

                output.write(
                    input_file.read()
                )

    return combined



# 15. RUN MAFFT


def run_mafft(input_fasta):

    mafft = shutil.which("mafft")

    if mafft is None:

        raise RuntimeError(
            "MAFFT was not found. "
            "Install it with: "
            "sudo apt install mafft"
        )

    output_file = (
        ALIGNMENT_DIR
        / f"{GENE}_alignment.fasta"
    )

    print()
    print("==========================================")
    print("RUNNING MAFFT")
    print("==========================================")

    with open(
        output_file,
        "w"
    ) as output:

        process = subprocess.run(
            [
                mafft,
                "--auto",
                str(input_fasta)
            ],
            stdout=output,
            stderr=subprocess.PIPE,
            text=True
        )

    if process.returncode != 0:

        print(process.stderr)

        raise RuntimeError(
            "MAFFT failed."
        )

    print(
        "Alignment saved:",
        output_file
    )

    return output_file



# 16. FIND IQ-TREE


def find_iqtree():

    for executable in [
        "iqtree3",
        "iqtree2",
        "iqtree"
    ]:

        path = shutil.which(executable)

        if path:
            return path

    return None



# 17. RUN IQ-TREE

def run_iqtree(alignment):

    iqtree = find_iqtree()

    if iqtree is None:

        raise RuntimeError(
            "IQ-TREE was not found."
        )

    prefix = (
        TREE_DIR
        / f"{GENE}_ML"
    )

    print()
    print("==========================================")
    print("RUNNING IQ-TREE")
    print("==========================================")

    command = [
        iqtree,

        "-redo",
        "-s",
        str(alignment),

        # Automatic model selection
        "-m",
        "TEST",

        # Ultrafast bootstrap
        "-bb",
        "1000",

        # SH-aLRT support
        "-alrt",
        "1000",

        # Output prefix
        "-pre",
        str(prefix)
    ]

    process = subprocess.run(
        command
    )

    if process.returncode != 0:

        raise RuntimeError(
            "IQ-TREE failed."
        )

    tree_file = Path(
        str(prefix)
        + ".treefile"
    )

    print(
        "Tree saved:",
        tree_file
    )

    return tree_file



# 18. SAVE ANALYSIS METADATA


def save_metadata(
    target,
    relatives,
    representatives,
    combined,
    alignment,
    tree
):

    result = {
        "target": target,

        "related_taxa": relatives,

        "representatives": representatives,

        "gene": GENE,

        "combined_fasta": str(
            combined
        ),

        "alignment": str(
            alignment
        ),

        "tree": str(
            tree
        )
    }

    filename = (
        RESULT_DIR
        / "analysis_metadata.json"
    )

    with open(
        filename,
        "w"
    ) as output:

        json.dump(
            result,
            output,
            indent=4
        )

    return filename



# 19. PRINT TAXONOMY


def print_taxonomy(taxonomy):

    print()
    print("==========================================")
    print("TAXONOMIC CLASSIFICATION")
    print("==========================================")

    print(
        "Scientific name:",
        taxonomy["scientific_name"]
    )

    print(
        "TaxID:",
        taxonomy["taxid"]
    )

    print(
        "Rank:",
        taxonomy["rank"]
    )

    print()

    for node in taxonomy["lineage"]:

        print(
            f"- {node['name']} "
            f"({node['rank']})"
        )



# 20. MAIN PIPELINE

def main():

    print()
    print("==========================================")
    print("       EVOLUTION ANALYSIS PIPELINE")
    print("==========================================")

    common_name = input(
        "\nEnter an animal: "
    ).strip()

    if not common_name:

        print(
            "No animal entered."
        )

        return


    # STEP 1

    print()
    print(
        "[1/9] Searching NCBI Taxonomy..."
    )

    taxids = search_taxonomy(
        common_name
    )

    if not taxids:

        print(
            "No taxonomy match found."
        )

        return

    print(
        "Taxonomy matches:"
    )

    taxon_candidates = []

    for taxid in taxids:

        try:

            summary = summarize_taxonomy(
                taxid
            )

        except Exception as error:

            print(
                f"Could not retrieve "
                f"TaxID {taxid}: {error}"
            )

            continue

        taxon_candidates.append(
            summary
        )

        print(
            f"  {taxid} | "
            f"{summary['scientific_name']} | "
            f"{summary['rank']}"
        )

    if not taxon_candidates:

        print(
            "Could not retrieve taxonomy."
        )

        return

    # STEP 2

    print()
    print(
        "[2/9] Selecting target species..."
    )

    # Current prototype:
    # choose the first species-level result.

    target = None

    for candidate in taxon_candidates:

        if candidate["rank"] == "species":

            target = candidate
            break

    if target is None:

        target = taxon_candidates[0]

    print(
        "Selected:",
        target["scientific_name"]
    )

    print_taxonomy(
        target
    )


    # STEP 3

    print()
    print(
        "[3/9] Finding related species..."
    )

    relatives = find_related_species(
        target
    )

    print(
        "Related species:"
    )

    for relative in relatives:

        print(
            "  -",
            relative["scientific_name"]
        )


    # STEP 4

    print()
    print(
        "[4/9] Building taxon dataset..."
    )

    taxa = [
        target
    ] + relatives

    unique_taxa = {}

    for taxon in taxa:

        unique_taxa[
            taxon["scientific_name"]
        ] = taxon

    taxa = list(
        unique_taxa.values()
    )

    print(
        "Total taxa to analyze:",
        len(taxa)
    )


    # STEP 5

    print()
    print(
        "[5/9] Retrieving and filtering COX1..."
    )

    sequence_files = []

    representatives = []

    successful_taxa = []

    for taxonomy in taxa:

        candidates = get_cox1_candidates(
            taxonomy
        )

        representative = select_representative(
            candidates
        )

        if representative is None:

            print(
                "No usable sequence for",
                taxonomy["scientific_name"]
            )

            continue

        print()
        print("REPRESENTATIVE")
        print(
            "Accession:",
            representative["accession"]
        )
        print(
            "Organism:",
            representative["organism"]
        )
        print(
            "COX1 length:",
            representative["length"],
            "bp"
        )

        fasta_file = save_species_sequence(
            representative
        )

        print(
            "Saved:",
            fasta_file
        )

        sequence_files.append(
            str(fasta_file)
        )

        representatives.append(
            representative
        )

        successful_taxa.append(
            taxonomy
        )

    print()
    print(
        "Species with usable sequences:",
        len(successful_taxa)
    )

    if len(successful_taxa) < 3:

        print()
        print(
            "At least 3 taxa are required "
            "for the initial phylogenetic "
            "analysis."
        )

        return


    # STEP 6

    print()
    print(
        "[6/9] Combining sequences..."
    )

    combined = combine_fastas(
        sequence_files
    )

    print(
        "Combined FASTA:",
        combined
    )

    # STEP 7

    print()
    print(
        "[7/9] Multiple sequence alignment..."
    )

    alignment = run_mafft(
        combined
    )

    # STEP 8


    print()
    print(
        "[8/9] Maximum-likelihood phylogeny..."
    )

    tree = run_iqtree(
        alignment
    )

    # STEP 9

    print()
    print(
        "[9/9] Saving analysis metadata..."
    )

    metadata = save_metadata(
        target,
        successful_taxa[1:],
        representatives,
        combined,
        alignment,
        tree
    )

    # FINAL RESULT


    print()
    print("==========================================")
    print("           ANALYSIS COMPLETE")
    print("==========================================")

    print()
    print(
        "Target:",
        target["scientific_name"]
    )

    print(
        "TaxID:",
        target["taxid"]
    )

    print()
    print(
        "Related taxa analyzed:"
    )

    for taxon in successful_taxa[1:]:

        print(
            "  -",
            taxon["scientific_name"]
        )

    print()
    print(
        "Combined FASTA:",
        combined
    )

    print(
        "Alignment:",
        alignment
    )

    print(
        "Phylogenetic tree:",
        tree
    )

    print(
        "Metadata:",
        metadata
    )

    print()
    print("IMPORTANT:")
    print(
        "This is a COX1 gene tree."
    )

    print(
        "It is not yet a dated evolutionary "
        "tree and cannot by itself determine "
        "the oldest known relative."
    )

    print()
    print(
        "Future stage:"
    )

    print(
        "Multiple markers + fossil calibrations "
        "+ molecular-clock analysis."
    )



# START

if __name__ == "__main__":
    main()
