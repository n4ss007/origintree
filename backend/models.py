"""The shape of everything the API returns.

Written down in one place so the interface has a contract to build against
rather than guessing from whatever a particular search happened to include.
Every field has a default, so a sparse NCBI record degrades to an empty value
instead of a 500.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class LineageNode(BaseModel):
    """One step on the path from the root of life to the organism."""

    name: str = ""
    rank: str = "no rank"
    taxid: str = ""
    major: bool = False


class Taxon(BaseModel):
    """A single taxonomy record, as shown to the user."""

    taxid: str = ""
    scientific_name: str = ""
    common_name: str = ""
    other_names: List[str] = Field(default_factory=list)
    rank: str = "no rank"
    division: str = ""
    genetic_code: str = ""
    parent_taxid: str = ""
    kingdom: str = ""
    lineage: List[LineageNode] = Field(default_factory=list)

    # why this record is in the results, and how strongly
    match_score: int = 0
    match_reason: str = ""
    source: str = "ncbi"


class SearchResponse(BaseModel):
    query: str = ""
    count: int = 0
    results: List[Taxon] = Field(default_factory=list)

    # true when the top matches are equally good but unrelated, e.g. "panda"
    # legitimately naming a bear, a red panda and a tree
    ambiguous: bool = False


class BarcodeWindow(BaseModel):
    """A short read of real bases from a taxon's best COX1 record.

    `bases` is always exactly WINDOW_BASES characters when available is true,
    and an empty string otherwise. It is never generated.
    """

    taxid: str = ""
    gene: str = ""
    available: bool = False
    bases: str = ""
    accession: str = ""
    organism: str = ""
    offset: int = 0
    length: int = 0


class FossilCalibration(BaseModel):
    """A dated fossil assigned to a clade, from the project's own dataset.

    This is the age of the oldest known fossil for the clade, which makes it
    a *minimum* age for that clade — not the date two species diverged.
    """

    clade: str = ""
    minimum_ma: Optional[float] = None
    maximum_ma: Optional[float] = None
    source: str = ""
    justification: str = ""
    matched_rank: str = ""
    taxid: str = ""


class Comparison(BaseModel):
    """Where two organisms' classifications agree, and where they part."""

    a: Taxon = Field(default_factory=Taxon)
    b: Taxon = Field(default_factory=Taxon)

    # "distinct" | "nested" | "identical"
    relationship: str = "distinct"
    summary: str = ""

    shared: List[LineageNode] = Field(default_factory=list)
    shared_count: int = 0
    common_ancestor: Optional[LineageNode] = None

    only_a: List[LineageNode] = Field(default_factory=list)
    only_b: List[LineageNode] = Field(default_factory=list)

    # present only when the shared path reaches a clade with a real fossil row
    fossil: Optional[FossilCalibration] = None


class BarcodeSide(BaseModel):
    accession: str = ""
    organism: str = ""
    length: int = 0


class BarcodeComparison(BaseModel):
    """How much two organisms' COX1 barcodes agree.

    `identity` is the percentage of aligned columns carrying the same base.
    Null whenever `available` is false — never estimated.
    """

    available: bool = False
    reason: str = ""
    gene: str = ""
    identity: Optional[float] = None
    matches: int = 0
    differences: int = 0
    aligned_length: int = 0
    a: Optional[BarcodeSide] = None
    b: Optional[BarcodeSide] = None


class SequenceRecord(BaseModel):
    accession: str = ""
    title: str = ""
    length: int = 0
    organism: str = ""
    complete: bool = False


class SequenceResponse(BaseModel):
    taxid: str = ""
    gene: str = ""
    count: int = 0
    sequences: List[SequenceRecord] = Field(default_factory=list)
    available: bool = False
