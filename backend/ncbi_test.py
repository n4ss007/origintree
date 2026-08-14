from Bio import Entrez, SeqIO

Entrez.email = "YOUR_EMAIL@example.com"
Entrez.tool = "EvolutionProject"


def find_species(search_term: str):
    """Search NCBI Taxonomy for the animal entered by the user."""

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


def fetch_sequences(
    taxid: str,
    scientific_name: str,
    gene: str = "COX1",
    max_sequences: int = 20
):
    """Retrieve COX1 sequences from NCBI."""

    search_term = f"txid{taxid}[Organism:exp] AND {gene}[Gene]"

    handle = Entrez.esearch(
        db="nuccore",
        term=search_term,
        retmax=max_sequences
    )

    result = Entrez.read(handle)
    handle.close()

    sequence_ids = result["IdList"]

    print(f"\nCandidate sequences found: {len(sequence_ids)}")

    if not sequence_ids:
        print("No candidate sequences found.")
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

        if "partial" in record.description.lower():
            print(
                f"REJECTED: {record.id} — partial sequence"
            )
            continue

        cox1_found = False

        for feature in record.features:

            if feature.type not in ["CDS", "gene"]:
                continue

            gene_name = ""

            if "gene" in feature.qualifiers:
                gene_name = feature.qualifiers["gene"][0].upper()

            if gene_name == gene.upper():

                sequence = feature.extract(record.seq)

                accepted.append(
                    {
                        "id": record.id,
                        "description": record.description,
                        "sequence": sequence
                    }
                )

                print(
                    f"ACCEPTED: {record.id} — COX1 extracted"
                )

                cox1_found = True
                break

        if not cox1_found:
            print(
                f"REJECTED: {record.id} — "
                f"COX1 feature not found"
            )

    print(
        f"\nAccepted COX1 sequences: {len(accepted)}"
    )

    if not accepted:
        print("No suitable COX1 sequences found.")
        return None

    safe_name = scientific_name.replace(" ", "_")

    filename = (
        f"data/sequences/"
        f"{safe_name}_COX1.fasta"
    )

    with open(filename, "w") as file:

        for item in accepted:

            file.write(
                f">{item['id']} {item['description']}\n"
            )

            file.write(
                str(item["sequence"]) + "\n"
            )

    print(f"Saved COX1 sequences to: {filename}")

    return filename


# --------------------------------
# USER INPUT
# --------------------------------

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

    fetch_sequences(
        taxid,
        result["scientific_name"]
    )
