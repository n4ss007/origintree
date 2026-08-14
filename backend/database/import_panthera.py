import sqlite3
from pathlib import Path
from datetime import date


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "evolution.db"

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()


# --------------------------------------------------
# 1. Add Panthera leo
# --------------------------------------------------

cursor.execute(
    """
    INSERT OR IGNORE INTO species
    (scientific_name, common_name, taxid, rank, lineage)
    VALUES (?, ?, ?, ?, ?)
    """,
    (
        "Panthera leo",
        "lion",
        9689,
        "species",
        "Animalia;Chordata;Mammalia;Carnivora;Felidae;Pantherinae;Panthera"
    )
)


cursor.execute(
    """
    SELECT id
    FROM species
    WHERE scientific_name = ?
    """,
    ("Panthera leo",)
)

species_id = cursor.fetchone()[0]


# --------------------------------------------------
# 2. Add molecular markers
# --------------------------------------------------

markers = {
    "COX1": "Mitochondrial cytochrome c oxidase subunit I",
    "ND1": "Mitochondrial NADH dehydrogenase subunit 1",
    "ND2": "Mitochondrial NADH dehydrogenase subunit 2",
    "RAG1": "Nuclear recombination activating gene 1",
    "RAG2": "Nuclear recombination activating gene 2",
}


for name, description in markers.items():

    cursor.execute(
        """
        INSERT OR IGNORE INTO markers
        (name, description)
        VALUES (?, ?)
        """,
        (name, description)
    )


# --------------------------------------------------
# 3. Add Panthera analysis
# --------------------------------------------------

alignment_file = (
    "results/panthera/"
    "multimarker_concatenated.fasta"
)

ml_tree_file = (
    "results/panthera/"
    "multimarker_ML.treefile"
)

dated_tree_file = None


cursor.execute(
    """
    INSERT INTO analyses
    (
        species_id,
        status,
        markers,
        alignment_file,
        ml_tree_file,
        dated_tree_file
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    (
        species_id,
        "complete_ml",
        "COX1,ND1,ND2,RAG1,RAG2",
        alignment_file,
        ml_tree_file,
        dated_tree_file
    )
)


# --------------------------------------------------
# 4. Add fossil calibration
# --------------------------------------------------

cursor.execute(
    """
    INSERT INTO fossils
    (
        clade,
        fossil_name,
        minimum_age_ma,
        maximum_age_ma,
        source,
        notes
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    (
        "Panthera",
        "Panthera blytheae",
        5.95,
        4.10,
        "Deng et al. 2014",
        "Fossil evidence relevant to the early Panthera lineage."
    )
)


connection.commit()


# --------------------------------------------------
# 5. Display result
# --------------------------------------------------

print()
print("==========================================")
print("PANTHERA DATA IMPORTED")
print("==========================================")

print("Species:")
print("  Panthera leo")

print("TaxID:")
print("  9689")

print("Markers:")
for marker in markers:
    print(f"  - {marker}")

print()
print("Analysis:")
print("  Multi-marker ML")

print()
print("Database:")
print(DB_PATH)

connection.close()

