from Bio import Entrez, SeqIO


Entrez.email = "shiforrandom@gmail.com"
Entrez.tool = "EvolutionProject"


def select_representative(
    fasta_file: str,
    target_species: str,
    min_length: int = 1500
):
    """Select a representative COX1 sequence belonging exactly
    to the requested species.
    """

    fasta_records = list(SeqIO.parse(fasta_file, "fasta"))

    if not fasta_records:
        print("No sequences found in FASTA file.")
        return None


    accessions = [record.id for record in fasta_records]

    print("Checking NCBI organism metadata...")


    handle = Entrez.efetch(
        db="nuccore",
        id=accessions,
        rettype="gb",
        retmode="text"
    )

    genbank_records = list(
        SeqIO.parse(handle, "genbank")
    )

    handle.close()

    candidates = []

    for record in genbank_records:

        organism = record.annotations.get(
            "organism",
            ""
        )

        print(
            f"{record.id}: {organism}"
        )


        if organism != target_species:
            continue

        sequence = str(record.seq).upper()


        if "N" in sequence:
            continue


        if len(sequence) < min_length:
            continue

        candidates.append(record)

    print(
        "\nEligible exact-species sequences:",
        len(candidates)
    )

    if not candidates:
        print(
            "No suitable representative found."
        )
        return None


    representative = max(
        candidates,
        key=lambda record: len(record.seq)
    )

    print("\nSelected representative:")
    print(
        "Accession:",
        representative.id
    )
    print(
        "Organism:",
        representative.annotations.get(
            "organism",
            "Unknown"
        )
    )
    print(
        "Length:",
        len(representative.seq)
    )
    print(
        "Description:",
        representative.description
    )

    return representative


# --------------------------------
# TEST
# --------------------------------

fasta_file = (
    "data/sequences/"
    "Panthera_leo_COX1.fasta"
)

target_species = "Panthera leo"


select_representative(
    fasta_file,
    target_species
)
