"""Fossil calibrations, read from the project's own dataset.

`data/fossils.csv` is curated by hand: one row per clade, each with a dated
fossil and the paper it comes from. It is small today — the pipeline uses it
to calibrate molecular dating — and this module simply makes it available to
the web layer, matched against a lineage.

Two rules keep this honest:

  * Only clades that are actually in the file get an age. Nothing is
    interpolated, estimated or filled in for a clade that has no row.
  * A calibration is the age of the *oldest known fossil* assigned to a
    clade, which makes it a minimum age for that clade — not the date two
    particular species diverged. The wording surfaced to the reader says so.

Adding calibrations means adding rows to the CSV. No code changes here.
"""

import csv
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FOSSIL_FILE = Path(
    os.environ.get("ORIGINTREE_FOSSIL_FILE", PROJECT_ROOT / "data" / "fossils.csv")
)

REQUIRED_COLUMNS = {"clade", "minimum_ma", "maximum_ma", "source", "justification"}

_cache = None


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_calibrations(path: Path = None) -> dict:
    """Every calibration in the dataset, keyed by lowercased clade name.

    Missing or malformed files yield an empty mapping rather than raising:
    a fossil dataset is supplementary, and its absence must not take the
    taxonomy API down with it.
    """

    source = Path(path) if path else FOSSIL_FILE

    if not source.is_file():
        return {}

    try:
        with open(source, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)

            if not REQUIRED_COLUMNS.issubset(set(reader.fieldnames or [])):
                return {}

            calibrations = {}

            for row in reader:
                clade = (row.get("clade") or "").strip()

                if not clade:
                    continue

                calibrations[clade.lower()] = {
                    "clade": clade,
                    "minimum_ma": _to_float(row.get("minimum_ma")),
                    "maximum_ma": _to_float(row.get("maximum_ma")),
                    "source": (row.get("source") or "").strip(),
                    "justification": (row.get("justification") or "").strip(),
                }

            return calibrations

    except (OSError, csv.Error, UnicodeDecodeError):
        return {}


def _calibrations(refresh: bool = False) -> dict:
    global _cache

    if _cache is None or refresh:
        _cache = load_calibrations()

    return _cache


def calibration_for_path(path: list, refresh: bool = False):
    """The most specific calibration covering a lineage, or None.

    `path` runs root-first, so walking it backwards finds the narrowest
    clade with a dated fossil — the one that says the most about the
    organisms in question.
    """

    calibrations = _calibrations(refresh)

    if not calibrations or not path:
        return None

    for step in reversed(path):
        match = calibrations.get((step.get("name") or "").strip().lower())

        if match:
            return dict(match, matched_rank=step.get("rank", ""), taxid=step.get("taxid", ""))

    return None
