"""Where two organisms' classifications agree, and where they part.

NCBI can tell you what a lion is. It cannot tell you that a lion and a snow
leopard share every rank down to the genus, while a lion and an octopus part
company back at Bilateria — answering that by hand means reading two
thirty-step lineages side by side and finding the first row that differs.

That comparison is what this module does. Nothing here touches the network:
it works on the taxonomy records the API already returns, which makes it
cheap and testable.

One thing this deliberately does NOT do is claim a date. A shared
classification says two organisms descend from a common ancestor; it says
nothing about when they diverged. Ages come only from fossil calibrations
where a real one exists — see fossils.py.
"""


def _full_path(taxon: dict) -> list:
    """The organism's lineage with the organism itself as the final step.

    NCBI's lineage is the path *to* a taxon and excludes it, but for a
    comparison the organism is a step like any other: it is what makes
    "Panthera leo vs Panthera" resolve to one containing the other.
    """

    path = list(taxon.get("lineage") or [])

    path.append(
        {
            "name": taxon.get("scientific_name", ""),
            "rank": taxon.get("rank", "no rank"),
            "taxid": str(taxon.get("taxid", "")),
            "major": True,
        }
    )

    return path


def _same_node(a: dict, b: dict) -> bool:
    """Two steps are the same step when NCBI gives them the same identifier.

    Compared on taxid rather than name: names repeat across kingdoms, and a
    homonym would otherwise read as shared ancestry.
    """

    left = str(a.get("taxid", ""))
    right = str(b.get("taxid", ""))

    if left and right:
        return left == right

    return a.get("name", "") == b.get("name", "")


def compare(taxon_a: dict, taxon_b: dict) -> dict:
    """Compare two taxonomy records.

    Returns the shared path, the last step they have in common, and what is
    left of each lineage after that point.

    `relationship` distinguishes the three shapes this can take:

      "distinct"   the usual case — they share a prefix, then diverge
      "nested"     one is inside the other (Panthera leo within Panthera)
      "identical"  the same taxon twice
    """

    path_a = _full_path(taxon_a)
    path_b = _full_path(taxon_b)

    shared = []

    for step_a, step_b in zip(path_a, path_b):
        if not _same_node(step_a, step_b):
            break
        shared.append(step_a)

    only_a = path_a[len(shared):]
    only_b = path_b[len(shared):]

    if not only_a and not only_b:
        relationship = "identical"
    elif not only_a or not only_b:
        relationship = "nested"
    else:
        relationship = "distinct"

    return {
        "relationship": relationship,
        "shared": shared,
        # the last rank they still have in common
        "common_ancestor": shared[-1] if shared else None,
        "shared_count": len(shared),
        "only_a": only_a,
        "only_b": only_b,
    }


def summarize(taxon_a: dict, taxon_b: dict, result: dict) -> str:
    """One plain sentence describing the result.

    Written for someone who does not read cladograms, and careful to say
    "classification" rather than anything implying a measured divergence.
    """

    name_a = taxon_a.get("common_name") or taxon_a.get("scientific_name", "")
    name_b = taxon_b.get("common_name") or taxon_b.get("scientific_name", "")
    ancestor = result.get("common_ancestor")

    if result["relationship"] == "identical":
        return f"{name_a} and {name_b} are the same taxon."

    if not ancestor:
        return (
            f"{name_a} and {name_b} share no classification in NCBI's record — "
            "not even a common root."
        )

    where = ancestor["name"]
    rank = ancestor.get("rank", "")
    rank_text = f" ({rank})" if rank and rank != "no rank" else ""

    if result["relationship"] == "nested":
        inner, outer = (name_a, name_b) if not result["only_a"] else (name_b, name_a)
        return f"{inner} sits inside {outer}: one is a subdivision of the other."

    steps_a = len(result["only_a"])
    steps_b = len(result["only_b"])
    step_word = "step" if steps_a == 1 else "steps"

    return (
        f"{name_a} and {name_b} share {result['shared_count']} ranks of "
        f"classification, down to {where}{rank_text}. After that their paths "
        f"separate — {steps_a} further {step_word} to {name_a}, {steps_b} to {name_b}."
    )
