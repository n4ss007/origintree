from Bio import Entrez, SeqIO

Entrez.email = "shiforrandom@example.com"
Entrez.tool = "EvolutionProject"

accessions = [
    "NC_028302.1",
    "NC_018053.1",
    "OP930842.1",
    "OP930841.1",
    "MT916290.1",
    "OK513019.1",
    "OK513012.1",
    "OK513011.1",
    "MW257216.1"
]

handle = Entrez.efetch(
    db="nuccore",
    id=accessions,
    rettype="gb",
    retmode="text"
)

records = SeqIO.parse(handle, "genbank")

for record in records:

    print("\n" + "=" * 70)

    print("Accession:", record.id)
    print("Description:", record.description)
    print("Length:", len(record.seq))

    organism = record.annotations.get(
        "organism",
        "Not available"
    )

    print("Organism:", organism)

    for key in [
        "isolate",
        "country",
        "collection_date"
    ]:

        values = record.annotations.get(key)

        if values:
            print(f"{key}:", values)

handle.close()
