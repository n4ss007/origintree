"""Scoring and ranking for taxonomy search results.

Nothing in this module touches the network. Everything here is a pure
function of its arguments, which is what makes the search behaviour
testable without hammering NCBI.

The problem this solves: NCBI's own result order is close to useless for
common-name searches. Asking for "seahorse" can put a virus genus above the
actual fish, because NCBI expands the term and then returns whatever matched
in taxid order. So we gather candidates broadly and decide the order here,
based on how well each record's real names match what the person typed.
"""

import re

# Score tiers. The gaps are wide on purpose: a record that merely contains
# the query as a fragment should never edge out one that genuinely is called
# that, no matter how many small bonuses it collects.
EXACT = 100
PLURAL = 90
ALL_WORDS = 70
FRAGMENT = 15

# Below this, a candidate is only worth showing if nothing better exists.
WEAK_MATCH = FRAGMENT + 1

# How precise an answer each rank represents. Used to break ties between
# equally-good name matches: asked for "panda", a species is a more useful
# answer than a genus. Ranks missing from this table score 0.
RANK_SPECIFICITY = {
    "superkingdom": 1,
    "domain": 1,
    "kingdom": 2,
    "phylum": 3,
    "subphylum": 3,
    "class": 4,
    "subclass": 4,
    "order": 5,
    "suborder": 5,
    "superfamily": 6,
    "family": 7,
    "subfamily": 8,
    "tribe": 8,
    "genus": 9,
    "subgenus": 9,
    "species group": 10,
    "species": 11,
    "subspecies": 12,
    "varietas": 12,
    "strain": 12,
}

# The ranks people are taught in biology class. The lineage of a single
# animal routinely runs past twenty-five entries once NCBI's unnamed clades
# are included, so the site shows these by default and folds away the rest.
MAJOR_RANKS = {
    "superkingdom",
    "domain",
    "kingdom",
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "species",
}

_PUNCTUATION = re.compile(r"[^\w\s]")
_WHITESPACE = re.compile(r"\s+")


def normalize(text) -> str:
    """Fold a name down to something comparable.

    Lowercases, turns hyphens into spaces, drops other punctuation and
    collapses runs of whitespace. "Sea-Horse" and "sea  horse" both become
    "sea horse".
    """

    if not text:
        return ""

    lowered = str(text).lower().replace("-", " ").replace("_", " ")
    stripped = _PUNCTUATION.sub("", lowered)

    return _WHITESPACE.sub(" ", stripped).strip()


def collapse_spaces(text: str) -> str:
    """"sea horse" -> "seahorse". NCBI stores many vernaculars as one word."""

    return normalize(text).replace(" ", "")


def plural_forms(term: str) -> set:
    """Regular English plural and singular variants of a normalized term.

    This is ordinary morphology, not a per-animal lookup table. It is what
    lets "seahorse" reach NCBI's "seahorses" and "tardigrade" reach
    "tardigrades" without anyone listing those animals anywhere.
    """

    term = normalize(term)
    if not term:
        return set()

    forms = {term}

    if term.endswith("y") and len(term) > 2 and term[-2] not in "aeiou":
        forms.add(term[:-1] + "ies")
    if term.endswith(("s", "x", "z", "ch", "sh")):
        forms.add(term + "es")
    else:
        forms.add(term + "s")

    # and the other direction, for someone who typed the plural
    if term.endswith("ies") and len(term) > 4:
        forms.add(term[:-3] + "y")
    if term.endswith("es") and len(term) > 3:
        forms.add(term[:-2])
    if term.endswith("s") and len(term) > 2:
        forms.add(term[:-1])

    return forms


def _words(text: str) -> list:
    return normalize(text).split()


def score_name(query: str, name: str) -> int:
    """How well one candidate name answers the query."""

    q = normalize(query)
    n = normalize(name)

    if not q or not n:
        return 0

    if q == n:
        return EXACT

    # "sea horse" typed against a stored "seahorse", or the reverse
    q_joined = collapse_spaces(q)
    n_joined = collapse_spaces(n)

    if q_joined == n_joined:
        return EXACT

    # The spacing and plural rules have to compose, not just run in turn.
    # NCBI's common name for Hippocampus is the single word "seahorses", so
    # "sea horse" only reaches it by collapsing the space *and* matching the
    # plural. Checking each rule on its own scores that pair zero.
    if n in plural_forms(q) or q in plural_forms(n):
        return PLURAL

    if n_joined in plural_forms(q_joined) or q_joined in plural_forms(n_joined):
        return PLURAL

    query_words = set(_words(q))
    name_words = set(_words(n))

    # every word the person typed appears as a whole word in the name:
    # "giant panda" against "Giant panda", or "panda" inside "giant panda"
    if query_words and query_words <= name_words:
        return ALL_WORDS

    # Anything left is the query appearing inside a longer word: "Pandanus"
    # for "panda", "Seahorsevirus" for "seahorse". A prefix that ends on a
    # word boundary has already been caught by the whole-word rule above, so
    # everything reaching here is a coincidence of spelling.
    if q in n:
        return FRAGMENT

    return 0


def best_match(query: str, names) -> tuple:
    """Score a record against all of its names.

    `names` is an iterable of (label, value) pairs, where label describes
    where the name came from ("scientific name", "common name", ...) so the
    interface can tell the user *why* something matched.

    Returns (score, reason, label) — the label lets the caller check whether
    the match came from the kind of name the person seemed to be typing.
    """

    best_score = 0
    best_reason = ""
    best_label = ""

    for label, value in names:
        if not value:
            continue

        score = score_name(query, value)

        if score > best_score:
            best_score = score
            best_reason = f'{label} "{value}"'
            best_label = label

    return best_score, best_reason, best_label


VERNACULAR_LABELS = {"common name", "common name via GBIF", "synonym", "equivalent name"}


def query_style(term: str) -> str:
    """Guess whether the person typed a formal name or an everyday one.

    Scientific names are capitalised by convention — "Panthera leo",
    "Hippocampus". Everyday names are not. Getting this wrong costs nothing
    beyond a tie being broken the other way.
    """

    stripped = (term or "").strip()

    if not stripped:
        return "vernacular"

    return "scientific" if stripped[0].isupper() else "vernacular"


def name_alignment(term: str, match_label: str) -> int:
    """1 when the matched name is the kind of name the query looked like.

    This is what separates equally-exact matches. Someone typing "panda" in
    lower case means the animal people call a panda, so a record matched on
    its common name is the better answer than a plant whose formal genus
    happens to be spelled Panda. Someone typing "Panda" gets the reverse.
    """

    if not match_label:
        return 0

    if query_style(term) == "scientific":
        return 1 if match_label == "scientific name" else 0

    return 1 if match_label in VERNACULAR_LABELS else 0


def rank_specificity(rank: str) -> int:
    return RANK_SPECIFICITY.get(normalize(rank), 0)


def sort_key(candidate: dict) -> tuple:
    """Ordering for scored candidates. Higher sorts first."""

    return (
        candidate.get("match_score", 0),
        # among equally-good matches, the kind of name that fits the query
        candidate.get("match_alignment", 0),
        # then: does NCBI itself call it this, or only the outside index?
        candidate.get("match_corroboration", 0),
        rank_specificity(candidate.get("rank", "")),
        # a settled scientific record over an unplaced one
        0 if normalize(candidate.get("rank", "")) in ("no rank", "clade", "") else 1,
    )


def rank_candidates(candidates: list, limit: int = 10) -> list:
    """Order candidates best-first and drop the ones that are only noise.

    Fragment-level matches (a query buried inside a longer word, which is how
    "Seahorsevirus" matches "seahorse") are dropped entirely once a genuine
    match exists. If nothing better turned up they are kept, because a weak
    answer still beats an empty page.
    """

    scored = [c for c in candidates if c.get("match_score", 0) > 0]

    if not scored:
        return []

    strong = [c for c in scored if c["match_score"] >= WEAK_MATCH]

    kept = strong if strong else scored
    kept.sort(key=sort_key, reverse=True)

    return kept[:limit]


def is_ambiguous(ranked: list) -> bool:
    """True when the top results are equally good but biologically unrelated.

    Searching "panda" genuinely matches a bear, a red panda, a catfish and a
    tree — all of them really are called that. The honest response is to say
    so rather than to pick one and present it as the answer.
    """

    if len(ranked) < 2:
        return False

    top = ranked[0]

    for other in ranked[1:]:
        if top["match_score"] - other.get("match_score", 0) > 10:
            break

        if other.get("kingdom") and top.get("kingdom"):
            if normalize(other["kingdom"]) != normalize(top["kingdom"]):
                return True

    return False
