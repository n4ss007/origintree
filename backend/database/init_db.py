import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "evolution.db"


connection = sqlite3.connect(DB_PATH)

cursor = connection.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS species (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scientific_name TEXT NOT NULL UNIQUE,
    common_name TEXT,
    taxid INTEGER,
    rank TEXT,
    lineage TEXT
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS markers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS sequences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    accession TEXT NOT NULL,
    species_id INTEGER,
    marker_id INTEGER,
    length INTEGER,
    source TEXT,
    retrieved_date TEXT,
    file_path TEXT,
    FOREIGN KEY (species_id) REFERENCES species(id),
    FOREIGN KEY (marker_id) REFERENCES markers(id)
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    species_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    markers TEXT,
    alignment_file TEXT,
    ml_tree_file TEXT,
    dated_tree_file TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (species_id) REFERENCES species(id)
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS fossils (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clade TEXT NOT NULL,
    fossil_name TEXT,
    minimum_age_ma REAL,
    maximum_age_ma REAL,
    source TEXT,
    notes TEXT
)
""")


connection.commit()
connection.close()


print(f"Database created successfully:")
print(DB_PATH)
