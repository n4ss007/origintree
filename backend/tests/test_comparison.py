"""Comparing two lineages, and the fossil lookup that hangs off it.

Offline: the comparison is pure logic, and the fossil dataset is a local
file. The lineages below are real NCBI paths, trimmed to the ranks that
matter for the case under test.
"""

import csv

from comparison import compare, summarize
from fossils import calibration_for_path, load_calibrations


def node(name, rank, taxid):
    return {"name": name, "rank": rank, "taxid": str(taxid), "major": True}


EUKARYOTA = node("Eukaryota", "domain", 2759)
METAZOA = node("Metazoa", "kingdom", 33208)
BILATERIA = node("Bilateria", "clade", 33213)
CHORDATA = node("Chordata", "phylum", 7711)
MAMMALIA = node("Mammalia", "class", 40674)
CARNIVORA = node("Carnivora", "order", 33554)
FELIDAE = node("Felidae", "family", 9681)
PANTHERA = node("Panthera", "genus", 9688)
MOLLUSCA = node("Mollusca", "phylum", 6447)


def taxon(name, taxid, lineage, rank="species", common=""):
    return {
        "scientific_name": name,
        "common_name": common,
        "taxid": str(taxid),
        "rank": rank,
        "lineage": lineage,
    }


LION = taxon(
    "Panthera leo", 9689,
    [EUKARYOTA, METAZOA, BILATERIA, CHORDATA, MAMMALIA, CARNIVORA, FELIDAE, PANTHERA],
    common="lion",
)
SNOW_LEOPARD = taxon(
    "Panthera uncia", 29064,
    [EUKARYOTA, METAZOA, BILATERIA, CHORDATA, MAMMALIA, CARNIVORA, FELIDAE, PANTHERA],
    common="snow leopard",
)
OCTOPUS = taxon(
    "Octopus vulgaris", 6645,
    [EUKARYOTA, METAZOA, BILATERIA, MOLLUSCA],
    common="common octopus",
)
PANTHERA_GENUS = taxon(
    "Panthera", 9688,
    [EUKARYOTA, METAZOA, BILATERIA, CHORDATA, MAMMALIA, CARNIVORA, FELIDAE],
    rank="genus",
)


# ---- shared ancestry ----------------------------------------------------


def test_close_relatives_share_everything_to_the_genus():
    result = compare(LION, SNOW_LEOPARD)

    assert result["relationship"] == "distinct"
    assert result["common_ancestor"]["name"] == "Panthera"
    # each keeps only itself after the split
    assert [n["name"] for n in result["only_a"]] == ["Panthera leo"]
    assert [n["name"] for n in result["only_b"]] == ["Panthera uncia"]


def test_distant_relatives_part_early():
    result = compare(LION, OCTOPUS)

    assert result["common_ancestor"]["name"] == "Bilateria"
    assert result["shared_count"] == 3
    # the lion keeps its whole vertebrate path after the split
    assert "Chordata" in [n["name"] for n in result["only_a"]]
    assert "Mollusca" in [n["name"] for n in result["only_b"]]


def test_a_taxon_inside_another_is_nested_not_diverged():
    result = compare(LION, PANTHERA_GENUS)

    assert result["relationship"] == "nested"
    assert result["only_b"] == []
    assert [n["name"] for n in result["only_a"]] == ["Panthera leo"]


def test_the_same_taxon_twice():
    result = compare(LION, LION)

    assert result["relationship"] == "identical"
    assert result["only_a"] == []
    assert result["only_b"] == []


def test_organisms_are_compared_on_taxid_not_name():
    """Names repeat across kingdoms. A homonym must not read as ancestry."""

    plant = taxon("Panda oleosa", 212258,
                  [EUKARYOTA, node("Viridiplantae", "kingdom", 33090),
                   node("Panda", "genus", 212257)])
    bear = taxon("Ailuropoda melanoleuca", 9646,
                 [EUKARYOTA, METAZOA, node("Panda", "genus", 999999)])

    result = compare(plant, bear)

    # they share only Eukaryota — the two "Panda" genera are different taxa
    assert result["shared_count"] == 1
    assert result["common_ancestor"]["name"] == "Eukaryota"


def test_nothing_in_common_yields_no_ancestor():
    a = taxon("A", 1, [node("Bacteria", "superkingdom", 2)])
    b = taxon("B", 2, [EUKARYOTA])

    result = compare(a, b)

    assert result["common_ancestor"] is None
    assert result["shared_count"] == 0


# ---- the sentence a reader actually sees --------------------------------


def test_summary_names_the_shared_rank():
    text = summarize(LION, SNOW_LEOPARD, compare(LION, SNOW_LEOPARD))

    assert "Panthera" in text
    assert "lion" in text and "snow leopard" in text


def test_summary_never_claims_a_divergence_date():
    """A shared classification says nothing about when two lineages split."""

    for pair in ((LION, OCTOPUS), (LION, SNOW_LEOPARD), (LION, PANTHERA_GENUS)):
        text = summarize(pair[0], pair[1], compare(*pair)).lower()

        for forbidden in ("years ago", "million years", "mya", " ma ", "diverged "):
            assert forbidden not in text


# ---- fossil calibrations ------------------------------------------------


def test_the_projects_own_calibration_loads():
    """data/fossils.csv is the real dataset, not a fixture."""

    calibrations = load_calibrations()

    assert "panthera" in calibrations
    assert calibrations["panthera"]["minimum_ma"] == 4.10


def test_a_calibration_is_found_for_a_matching_clade():
    shared = compare(LION, SNOW_LEOPARD)["shared"]

    fossil = calibration_for_path(shared)

    assert fossil is not None
    assert fossil["clade"] == "Panthera"
    assert fossil["source"]


def test_no_calibration_is_invented_for_a_clade_without_one():
    shared = compare(LION, OCTOPUS)["shared"]

    assert calibration_for_path(shared) is None


def test_the_most_specific_calibration_wins(tmp_path):
    path = tmp_path / "fossils.csv"

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["clade", "minimum_ma", "maximum_ma", "source", "justification"])
        writer.writerow(["Mammalia", "160", "170", "src", "why"])
        writer.writerow(["Panthera", "4.1", "5.95", "src", "why"])

    import fossils

    fossils._cache = fossils.load_calibrations(path)
    try:
        found = calibration_for_path([MAMMALIA, CARNIVORA, FELIDAE, PANTHERA])
        assert found["clade"] == "Panthera"
    finally:
        fossils._cache = None


def test_a_missing_dataset_degrades_quietly(tmp_path):
    """Fossils are supplementary; their absence must not break taxonomy."""

    assert load_calibrations(tmp_path / "does_not_exist.csv") == {}
