"""Ranking tests.

These run offline. Each one pins down a specific way the old search went
wrong, using the names NCBI really holds for those organisms.
"""

from ranking import (
    ALL_WORDS,
    EXACT,
    FRAGMENT,
    PLURAL,
    collapse_spaces,
    is_ambiguous,
    name_alignment,
    normalize,
    plural_forms,
    query_style,
    rank_candidates,
    score_name,
)


# ---- normalizing --------------------------------------------------------


def test_normalize_folds_case_punctuation_and_spacing():
    assert normalize("  Sea-Horse  ") == "sea horse"
    assert normalize("Panthera leo (Linnaeus)") == "panthera leo linnaeus"
    assert normalize(None) == ""


def test_collapse_spaces_joins_words():
    assert collapse_spaces("sea horse") == "seahorse"


# ---- plural morphology --------------------------------------------------


def test_plural_forms_are_general_not_a_lookup_table():
    assert "seahorses" in plural_forms("seahorse")
    assert "tardigrades" in plural_forms("tardigrade")
    assert "foxes" in plural_forms("fox")
    assert "butterflies" in plural_forms("butterfly")
    # and back the other way
    assert "seahorse" in plural_forms("seahorses")


# ---- scoring ------------------------------------------------------------


def test_exact_match_scores_highest():
    assert score_name("lion", "lion") == EXACT
    assert score_name("Panthera leo", "panthera leo") == EXACT


def test_spacing_difference_still_counts_as_exact():
    """"sea horse" typed against NCBI's stored "seahorses" family of names."""
    assert score_name("sea horse", "seahorse") == EXACT


def test_plural_stored_name_is_reachable():
    """NCBI stores "seahorses", never "seahorse"."""
    assert score_name("seahorse", "seahorses") == PLURAL
    assert score_name("tardigrade", "tardigrades") == PLURAL


def test_spacing_and_plural_rules_compose():
    """NCBI's common name for Hippocampus is the single word "seahorses", so
    "sea horse" only reaches it by collapsing the space *and* matching the
    plural. Applying the rules separately scores this pair zero."""

    assert score_name("sea horse", "seahorses") == PLURAL
    assert score_name("seahorses", "sea horse") == PLURAL
    assert score_name("sea horses", "seahorse") == PLURAL


def test_whole_word_containment():
    assert score_name("panda", "giant panda") == ALL_WORDS
    assert score_name("giant panda", "giant panda") == EXACT


def test_leading_word_of_a_binomial_matches_as_a_whole_word():
    assert score_name("panthera", "Panthera leo") == ALL_WORDS


def test_a_prefix_that_runs_into_another_word_is_only_a_fragment():
    """Spelling coincidences, not matches. This is the junk NCBI's wildcard
    drags in: Pandanus and Pandalus for "panda", Seahorsevirus for "seahorse"."""

    assert score_name("seahorse", "seahorsevirus") == FRAGMENT
    assert score_name("panda", "Pandanus") == FRAGMENT
    assert score_name("panda", "Pandalus") == FRAGMENT


def test_unrelated_name_scores_nothing():
    assert score_name("panda", "Ailuropoda") == 0
    assert score_name("lion", "Anolis") == 0


def test_fragment_matches_are_filtered_out_by_ranking():
    """Scoring low is only half the fix; they must also be dropped."""

    ranked = rank_candidates(
        [
            _taxon("Pandanus", score_name("panda", "Pandanus"), rank="genus"),
            _taxon("Panda", score_name("panda", "Panda"), rank="genus"),
        ]
    )

    assert [r["scientific_name"] for r in ranked] == ["Panda"]


# ---- ranking ------------------------------------------------------------


def _taxon(name, score, rank="species", kingdom="Metazoa"):
    return {
        "scientific_name": name,
        "match_score": score,
        "rank": rank,
        "kingdom": kingdom,
    }


def test_virus_fragment_match_is_dropped_when_a_real_match_exists():
    """The seahorse bug: Seahorsevirus must not sit alongside Hippocampus."""

    ranked = rank_candidates(
        [
            _taxon("Seahorsevirus", FRAGMENT, rank="genus", kingdom="Viruses"),
            _taxon("Hippocampinae", PLURAL, rank="subfamily"),
        ]
    )

    names = [r["scientific_name"] for r in ranked]

    assert names == ["Hippocampinae"]


def test_weak_match_is_kept_when_it_is_all_there_is():
    ranked = rank_candidates([_taxon("Seahorsevirus", FRAGMENT, kingdom="Viruses")])

    assert len(ranked) == 1


def test_species_outranks_genus_on_an_equal_name_match():
    ranked = rank_candidates(
        [
            _taxon("Panda", EXACT, rank="genus", kingdom="Viridiplantae"),
            _taxon("Ailuropoda melanoleuca", EXACT, rank="species"),
        ]
    )

    assert ranked[0]["scientific_name"] == "Ailuropoda melanoleuca"


def test_stronger_name_match_beats_a_more_specific_rank():
    ranked = rank_candidates(
        [
            _taxon("Something specific", FRAGMENT + 5, rank="subspecies"),
            _taxon("Exactly it", EXACT, rank="family"),
        ]
    )

    assert ranked[0]["scientific_name"] == "Exactly it"


def test_ranking_respects_the_limit():
    candidates = [_taxon(f"Taxon {i}", EXACT) for i in range(10)]

    assert len(rank_candidates(candidates, limit=3)) == 3


def test_empty_input_gives_empty_output():
    assert rank_candidates([]) == []
    assert rank_candidates([_taxon("No match", 0)]) == []


# ---- matching the kind of name to the kind of query ---------------------


def test_query_style_reads_capitalisation():
    assert query_style("panda") == "vernacular"
    assert query_style("Panthera leo") == "scientific"
    assert query_style("Hippocampus") == "scientific"


def test_lowercase_query_prefers_a_common_name_match():
    assert name_alignment("panda", "common name") == 1
    assert name_alignment("panda", "scientific name") == 0


def test_capitalised_query_prefers_a_scientific_name_match():
    assert name_alignment("Panda", "scientific name") == 1
    assert name_alignment("Panda", "common name") == 0


def test_alignment_breaks_a_tie_between_equal_matches():
    """The panda case: a bear known as "panda" beats a tree formally named
    Panda when the query was typed in lower case."""

    bear = _taxon("Ailuropoda melanoleuca", EXACT)
    bear["match_alignment"] = name_alignment("panda", "common name")

    tree = _taxon("Panda oleosa", EXACT, kingdom="Viridiplantae")
    tree["match_alignment"] = name_alignment("panda", "scientific name")

    ranked = rank_candidates([tree, bear])

    assert ranked[0]["scientific_name"] == "Ailuropoda melanoleuca"
    # both are still shown, because both really are called panda
    assert len(ranked) == 2


# ---- ambiguity ----------------------------------------------------------


def test_equally_good_matches_in_different_kingdoms_are_ambiguous():
    """"panda" really does name both a bear and a tree."""

    ranked = [
        _taxon("Ailuropoda melanoleuca", EXACT, kingdom="Metazoa"),
        _taxon("Panda oleosa", EXACT, kingdom="Viridiplantae"),
    ]

    assert is_ambiguous(ranked) is True


def test_same_kingdom_matches_are_not_ambiguous():
    ranked = [
        _taxon("Hippocampus hippocampus", EXACT),
        _taxon("Hippocampus kuda", EXACT),
    ]

    assert is_ambiguous(ranked) is False


def test_a_clear_winner_is_not_ambiguous():
    ranked = [
        _taxon("Panthera leo", EXACT),
        _taxon("Something else", FRAGMENT, kingdom="Viruses"),
    ]

    assert is_ambiguous(ranked) is False


def test_single_result_is_not_ambiguous():
    assert is_ambiguous([_taxon("Homo sapiens", EXACT)]) is False
