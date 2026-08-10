from Bio import Entrez

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
