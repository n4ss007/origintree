import csv
from pathlib import Path


fossil_file = Path("data/fossils.csv")

if not fossil_file.exists():
    raise FileNotFoundError(
        "data/fossils.csv not found."
    )


with open(
    fossil_file,
    newline=""
) as handle:

    reader = csv.DictReader(handle)

    required = {
        "clade",
        "minimum_ma",
        "maximum_ma",
        "source",
        "justification"
    }

    missing = (
        required
        - set(reader.fieldnames or [])
    )

    if missing:
        raise ValueError(
            f"Missing columns: {missing}"
        )

    fossils = list(reader)


print()
print("==========================================")
print("FOSSIL CALIBRATIONS")
print("==========================================")

for fossil in fossils:

    minimum = float(
        fossil["minimum_ma"]
    )

    maximum = float(
        fossil["maximum_ma"]
    )

    if minimum <= 0:
        raise ValueError(
            "Fossil age must be greater than 0."
        )

    if maximum < minimum:
        raise ValueError(
            "Maximum age cannot be younger "
            "than minimum age."
        )

    print()
    print("Clade:", fossil["clade"])
    print(
        "Age:",
        f"{minimum}–{maximum} Ma"
    )
    print(
        "Source:",
        fossil["source"]
    )
    print(
        "Justification:",
        fossil["justification"]
    )


print()
print(
    f"Valid fossil calibrations: {len(fossils)}"
)
