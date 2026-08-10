from Bio import Entrez, SeqIO

Entrez.email = "shiforrandom@gmail.com"
Entrez.tool = "EvolutionProject"
def find_species(search_term: str):
    """Search NCBI Taxonomy for an organism entered by the user."""

    handle = Entrez.esearch(
        db="taxonomy",
        term=search_term,
        retmax=10
    )

    result = Entrez.read(handle)
    handle.close()

    return result["IdList"]


def get_taxonomy_record(taxid: str):
    """Retrieve the complete NCBI taxonomy record."""

    handle = Entrez.efetch(
        db="taxonomy",
        id=taxid,
        retmode="xml"
    )

    records = Entrez.read(handle)
    handle.close()

    return records[0]


def summarize_species(taxid: str) -> dict:
    """Extract the taxonomy information we need."""

    record = get_taxonomy_record(taxid)

    scientific_name = record["ScientificName"]
    rank = record["Rank"]

    lineage = [
        {
            "name": node["ScientificName"],
            "rank": node["Rank"]
        }
        for node in record["LineageEx"]
    ]

    return {
        "taxid": taxid,
        "scientific_name": scientific_name,
        "rank": rank,
        "lineage": lineage
    }


def fetch_sequences(taxid: str, scientific_name:str, gene: str = "COX1", max_sequences: int = 5):
    """Retrieve nucleotide sequences and save them as a fasta file."""

    search_term = f"txid{taxid}[Organism:exp] AND {gene}[Gene]"

    handle = Entrez.esearch(
        db="nuccore",
        term=search_term,
        retmax=max_sequences
    )

    result = Entrez.read(handle)
    handle.close()

    sequence_ids = result["IdList"]

    print(f"\nFound {len(sequence_ids)} sequences.")

    if not sequence_ids:
        print("No sequences found.")
        return None

    handle = Entrez.efetch(
        db="nuccore",
        id=sequence_ids,
        rettype="gb",
        retmode="text"
    )
    records = list(SeqIO.parse(handle, "genbank"))
    handle.close()

    accepted = []

    for record in records:

        description = record.description.lower()

        if "partial" in description:

            print(f"REJECTED: {record.id} — partial sequence")
            continue

        if "cox1" not in description and "cytochrome c oxidase subunit i" not in description:
            print(f"REJECTED: {record.id} — COX1 not confirmed")
            continue

        print(f"ACCEPTED: {record.id} — {record.description}")

        accepted.append(record)

    print(f"\nAccepted sequences: {len(accepted)}")

    if not accepted:
        print("No suitable complete COX1 sequences found.")
        return None

    safe_name = scientific_name.replace(" ", "_")

    filename = (
        f"data/sequences/"
        f"{safe_name}_COX1.fasta"
)

    with open(filename, "w") as file:

        for record in accepted:
            file.write(f">{record.id} {record.description}\n")
            file.write(str(record.seq) + "\n")

    print(f"Saved selected sequences to: {filename}")

    return filename


# -----------------------------
# USER INPUT
# -----------------------------

common_name = input("Enter an animal: ")

taxids = find_species(common_name)

print("\nTaxonomy matches found:", len(taxids))

for taxid in taxids:
    result = summarize_species(taxid)


    print("\n-----------------------------")
    print("TaxID:", result["taxid"])
    print("Scientific name:", result["scientific_name"])
    print("Rank:", result["rank"])
    print("\nTaxonomic lineage:")

    for node in result["lineage"]:
        print(
            f"- {node['name']} ({node['rank']})"
        )

    sequence_file = fetch_sequences(
        taxid,
        result["scientific_name"]
    )
