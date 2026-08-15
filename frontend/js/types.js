/**
 * The shape of everything the API returns.
 *
 * Mirrors backend/models.py. Kept as JSDoc rather than TypeScript because the
 * project has no build step; editors still read these for completion and
 * type checking.
 *
 * Every field is always present. Fields NCBI has no value for arrive as an
 * empty string or an empty array, never as null or missing, so views can
 * render "not recorded" instead of guarding every access.
 */

/**
 * One step on the path from the root of life to an organism.
 *
 * @typedef  {object}  LineageNode
 * @property {string}  name    Scientific name of this step, e.g. "Carnivora"
 * @property {string}  rank    e.g. "order", "clade", "no rank"
 * @property {string}  taxid   NCBI identifier for this step
 * @property {boolean} major   True for the ranks taught in biology class.
 *                             NCBI lineages run past 25 entries once unnamed
 *                             clades are counted, so the tree shows these by
 *                             default and folds the rest away.
 */

/**
 * A single taxonomy record.
 *
 * @typedef  {object}   Taxon
 * @property {string}   taxid
 * @property {string}   scientific_name
 * @property {string}   common_name      Often empty; fall back to scientific_name
 * @property {string[]} other_names      Synonyms and further common names
 * @property {string}   rank
 * @property {string}   division         NCBI grouping, e.g. "Mammals"
 * @property {string}   genetic_code     e.g. "Standard"
 * @property {string}   parent_taxid
 * @property {string}   kingdom          Broad group read from the lineage
 * @property {LineageNode[]} lineage     Path TO the organism; excludes it
 * @property {number}   match_score      100 exact, 90 plural, 70 whole-word,
 *                                       15 fragment
 * @property {string}   match_reason     Why it matched, e.g. common name "lion"
 * @property {string}   source           "ncbi" or "gbif-resolved"
 */

/**
 * @typedef  {object}  SearchResponse
 * @property {string}  query
 * @property {number}  count
 * @property {Taxon[]} results
 * @property {boolean} ambiguous  True when the top matches are equally good
 *                                but unrelated, e.g. "panda" naming a bear,
 *                                a red panda and a tree
 */

/**
 * @typedef  {object}  SequenceRecord
 * @property {string}  accession
 * @property {string}  title
 * @property {number}  length     Base pairs
 * @property {string}  organism
 * @property {boolean} complete   False when GenBank calls it a partial cds
 */

/**
 * @typedef  {object}           SequenceResponse
 * @property {string}           taxid
 * @property {string}           gene       e.g. "COX1"
 * @property {number}           count      Total held by NCBI, not just listed
 * @property {SequenceRecord[]} sequences
 * @property {boolean}          available
 */

/**
 * A short read of real bases from a taxon's best COX1 record.
 *
 * `bases` is exactly 8 characters, read directly from GenBank, whenever
 * `available` is true — never generated, padded, or substituted. When
 * `available` is false every other field is empty or zero.
 *
 * @typedef  {object}  BarcodeWindow
 * @property {string}  taxid
 * @property {string}  gene        e.g. "COX1"
 * @property {boolean} available
 * @property {string}  bases       Exactly 8 characters when available
 * @property {string}  accession   GenBank accession the bases were read from
 * @property {string}  organism
 * @property {number}  offset      Position of the window within the record
 * @property {number}  length      Length of the full record, in bases
 */

/**
 * A dated fossil assigned to a clade, from the project's own dataset.
 *
 * This is the age of the OLDEST KNOWN FOSSIL for the clade, which makes it a
 * minimum age for that group — not the date two lineages diverged. Present
 * only when data/fossils.csv actually holds a row for the clade; never
 * estimated or interpolated.
 *
 * @typedef  {object}  FossilCalibration
 * @property {string}  clade
 * @property {number|null} minimum_ma
 * @property {number|null} maximum_ma
 * @property {string}  source          the paper it comes from
 * @property {string}  justification
 * @property {string}  matched_rank
 * @property {string}  taxid
 */

/**
 * Where two organisms' classifications agree, and where they part.
 *
 * `shared` runs root-first and ends at `common_ancestor`; `only_a`/`only_b`
 * are what remains of each path after that point. `relationship` is
 * "distinct", "nested" (one inside the other) or "identical".
 *
 * @typedef  {object}        Comparison
 * @property {Taxon}         a
 * @property {Taxon}         b
 * @property {string}        relationship
 * @property {string}        summary        one plain sentence
 * @property {LineageNode[]} shared
 * @property {number}        shared_count
 * @property {LineageNode|null} common_ancestor
 * @property {LineageNode[]} only_a
 * @property {LineageNode[]} only_b
 * @property {FossilCalibration|null} fossil
 */

/**
 * How much two organisms' COX1 barcodes agree.
 *
 * `identity` is the percentage of aligned columns carrying the same base,
 * from a local alignment of the best confirmed record for each organism.
 * Null whenever `available` is false — never estimated, and refused rather
 * than reported when the two records overlap too little to mean anything.
 *
 * @typedef  {object}  BarcodeComparison
 * @property {boolean} available
 * @property {string}  reason          why it is unavailable, when it is
 * @property {string}  gene
 * @property {number|null} identity
 * @property {number}  matches
 * @property {number}  differences
 * @property {number}  aligned_length
 * @property {{accession: string, organism: string, length: number}|null} a
 * @property {{accession: string, organism: string, length: number}|null} b
 */

/* ---------------------------------------------------------------
   Extension points

   The backend is still growing. These are the seams where new strands of
   data are expected to arrive, recorded so the shape of the frontend does
   not have to change when they do.

   Nothing below is implemented, and none of it is faked anywhere in the
   interface: a strand appears only once the backend genuinely returns it.

   The separation that matters is already in place:

     ORGANISM    identity — names, rank, TaxID           (Taxon, above)
     TAXONOMY    ancestry — the lineage and its ranks     (LineageNode)
     SEQUENCE    molecular evidence — COX1 reads          (SequenceRecord,
                                                           BarcodeWindow)
     FUTURE      fossils, geological time, evolutionary
                 relationships, other databases

   Each is rendered by its own section builder in results.js, listed in one
   place in renderResults(). A new strand means a new endpoint in api.js, a
   typedef here, and a builder added to that list — no change to the ones
   already there.

   Likely shapes, for orientation only. Treat the backend as authoritative
   when these actually land, not this comment:

     FossilOccurrence   taxid, site, epoch, age_mya, source, source_id
     TemporalRange      taxid, first_appearance_mya, last_appearance_mya
     Relationship       from_taxid, to_taxid, kind, evidence, source
     SourceRef          database, identifier, url, retrieved

   Every one of those carries its own `source`, because a fact from a second
   database must remain attributable to that database rather than being
   folded into NCBI's record.
   --------------------------------------------------------------- */

export {};
