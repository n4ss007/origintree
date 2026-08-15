/**
 * Renders every state that can appear in the results region: loading,
 * error, no-results, and the results themselves, split into the three
 * sections the page structure calls for — EXPLORATION (the ambiguous
 * notice and the pick-one list, when there's a choice to make), LINEAGE
 * (the tree, delegated to tree.js), and ORGANISM (the record, its barcode
 * motif, and the molecular evidence panel).
 *
 * This module also owns the scroll-reveal used by every section on the
 * page after the hero — including the two static ones already sitting in
 * index.html — so there is exactly one IntersectionObserver on the page
 * rather than one per module.
 */

import { fetchSequences, ApiError } from "./api.js";
import { renderTree } from "./tree.js";
import { renderBarcode } from "./barcode.js";
import { renderCompare } from "./compare.js";
import { createLoader } from "./loader.js";

const SVG_NS = "http://www.w3.org/2000/svg";

/* ---------------------------------------------------------------
   Scroll reveal
   --------------------------------------------------------------- */

const revealObserver =
  "IntersectionObserver" in window
    ? new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-visible");
              revealObserver.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
      )
    : null;

/** Marks `el` to fade/rise into place once, the first time it enters the
 *  viewport, and never again. Safe to call on elements that are already
 *  on screen — they simply reveal on the next frame. */
export function registerReveal(el) {
  el.classList.add("reveal");
  if (revealObserver) {
    revealObserver.observe(el);
  } else {
    el.classList.add("is-visible");
  }
}

/* ---------------------------------------------------------------
   Transient states
   --------------------------------------------------------------- */

/**
 * The loader runs on a timer, so exactly one may exist at a time and it has
 * to be stopped the moment anything else is painted. Every render function
 * below calls this first.
 */
let activeLoader = null;

function stopActiveLoader() {
  if (activeLoader) {
    activeLoader.stop();
    activeLoader = null;
  }
}

export function renderLoading(container, query) {
  stopActiveLoader();
  clearNode(container);

  const state = document.createElement("div");
  state.className = "state state-loading";

  activeLoader = createLoader(
    query ? `Tracing lineage for “${query}”…` : "Tracing lineage…"
  );
  state.appendChild(activeLoader.el);

  container.appendChild(state);
}


export function renderError(container, error, { onRetry } = {}) {
  stopActiveLoader();
  clearNode(container);

  const state = document.createElement("div");
  state.className = "state state-error";

  const title = document.createElement("p");
  title.className = "state-title";

  const message = document.createElement("p");

  const offline = error instanceof ApiError && error.kind === "offline";

  if (offline) {
    title.textContent = "The OriginTree server isn't running.";
    message.textContent = "Start the backend, then try your search again:";
    state.appendChild(title);
    state.appendChild(message);

    const pre = document.createElement("pre");
    pre.className = "state-command";
    const code = document.createElement("code");
    code.textContent = "uvicorn main:app --reload --app-dir backend";
    pre.appendChild(code);
    state.appendChild(pre);
  } else {
    title.textContent = "That search couldn't be completed.";
    message.textContent =
      (error && error.message) || "Something went wrong reaching NCBI Taxonomy.";
    state.appendChild(title);
    state.appendChild(message);
  }

  if (onRetry) {
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "retry-button";
    retry.textContent = "Try again";
    retry.addEventListener("click", onRetry);
    state.appendChild(retry);
  }

  container.appendChild(state);
}

export function renderEmpty(container, query) {
  stopActiveLoader();
  clearNode(container);

  const state = document.createElement("div");
  state.className = "state state-empty";

  const title = document.createElement("p");
  title.className = "state-title";
  title.textContent = `No record of “${query}” in NCBI Taxonomy.`;
  state.appendChild(title);

  const message = document.createElement("p");
  message.textContent =
    "Check the spelling, or try a common name instead of a scientific one — the examples above are all known to work.";
  state.appendChild(message);

  container.appendChild(state);
}

/* ---------------------------------------------------------------
   Results
   --------------------------------------------------------------- */

let sectionIdCounter = 0;

export function renderResults(container, response, { selectedIndex, onSelect }) {
  stopActiveLoader();
  clearNode(container);

  const view = document.createElement("div");
  view.className = "result-view";
  const uid = `res-${++sectionIdCounter}`;

  const hasChoice = response.ambiguous || response.results.length > 1;

  let exploration = null;
  if (hasChoice) {
    exploration = buildExploration(response, selectedIndex, onSelect, uid);
    view.appendChild(exploration);
  }

  const taxon = response.results[selectedIndex];

  // Order matters: what it is, then where it came from, then the underlying
  // data. Each entry is a section builder, so a future strand — fossils,
  // geological time, cross-database links — is added by writing a builder
  // and listing it here, without touching the ones above it.
  const sections = [];

  if (taxon) {
    sections.push(
      buildOrganismSection(taxon, uid),
      buildLineageSection(taxon, uid),
      buildComparisonSection(taxon),
      buildScientificDataSection(taxon, uid)
    );
    sections.forEach((section) => view.appendChild(section));
  }

  container.appendChild(view);

  if (exploration) registerReveal(exploration);
  sections.forEach(registerReveal);
}

/* ---------------------------------------------------------------
   EXPLORATION — the ambiguous notice and the pick-one list
   --------------------------------------------------------------- */

function buildExploration(response, selectedIndex, onSelect, uid) {
  const section = document.createElement("section");
  section.className = "exploration";
  section.setAttribute("aria-labelledby", `${uid}-exploration-heading`);

  if (response.ambiguous) {
    section.appendChild(buildAmbiguousNotice(response.query));
  }

  if (response.results.length > 1) {
    section.appendChild(buildSelection(response.results, selectedIndex, onSelect, uid));
  }

  return section;
}

function buildAmbiguousNotice(query) {
  const notice = document.createElement("div");
  notice.className = "notice-ambiguous";
  notice.setAttribute("role", "note");

  const mark = document.createElementNS(SVG_NS, "svg");
  mark.setAttribute("class", "notice-ambiguous-mark");
  mark.setAttribute("width", "16");
  mark.setAttribute("height", "16");
  mark.setAttribute("viewBox", "0 0 16 16");
  mark.setAttribute("aria-hidden", "true");
  const circle = document.createElementNS(SVG_NS, "circle");
  circle.setAttribute("cx", "8");
  circle.setAttribute("cy", "8");
  circle.setAttribute("r", "6.2");
  circle.setAttribute("fill", "none");
  circle.setAttribute("stroke", "currentColor");
  circle.setAttribute("stroke-width", "1.4");
  mark.appendChild(circle);
  const dot = document.createElementNS(SVG_NS, "circle");
  dot.setAttribute("cx", "8");
  dot.setAttribute("cy", "8");
  dot.setAttribute("r", "1.4");
  dot.setAttribute("fill", "currentColor");
  mark.appendChild(dot);
  notice.appendChild(mark);

  const p = document.createElement("p");
  const strong = document.createElement("strong");
  strong.textContent = `Several unrelated organisms share the name “${query}.” `;
  p.appendChild(strong);
  p.appendChild(
    document.createTextNode(
      "They are matched on the name alone, not on how closely they are related. Pick the one you meant below."
    )
  );
  notice.appendChild(p);

  return notice;
}

function buildSelection(results, selectedIndex, onSelect, uid) {
  const section = document.createElement("div");
  section.className = "selection";

  const heading = document.createElement("h3");
  heading.id = `${uid}-exploration-heading`;
  heading.className = "selection-heading";
  heading.textContent = `${results.length} organisms match — choose one`;
  section.appendChild(heading);

  const list = document.createElement("ul");
  list.className = "selection-list";

  results.forEach((taxon, index) => {
    const li = document.createElement("li");
    const card = document.createElement("button");
    card.type = "button";
    card.className = "selection-card";
    card.setAttribute("aria-pressed", String(index === selectedIndex));

    const name = document.createElement("span");
    name.className = "selection-card-name";
    name.textContent = taxon.common_name || taxon.scientific_name;
    card.appendChild(name);

    if (taxon.common_name) {
      const sci = document.createElement("span");
      sci.className = "selection-card-sci";
      sci.textContent = taxon.scientific_name;
      card.appendChild(sci);
    }

    if (taxon.match_reason) {
      const reason = document.createElement("span");
      reason.className = "selection-card-reason";
      reason.textContent = `matched ${taxon.match_reason}`;
      card.appendChild(reason);
    }

    card.addEventListener("click", () => onSelect(index));
    li.appendChild(card);
    list.appendChild(li);
  });

  section.appendChild(list);
  return section;
}

/* ---------------------------------------------------------------
   LINEAGE — the signature tree
   --------------------------------------------------------------- */

/** A section label: one heading, no eyebrow restating it underneath. */
function buildSectionHeading(text, headingId) {
  const heading = document.createElement("h3");
  heading.id = headingId;
  heading.className = "section-heading";
  heading.textContent = text;
  return heading;
}

function buildLineageSection(taxon, uid) {
  const section = document.createElement("section");
  section.className = "lineage-section";
  const headingId = `${uid}-lineage-heading`;
  section.setAttribute("aria-labelledby", headingId);

  section.appendChild(buildSectionHeading("Taxonomic lineage", headingId));

  const treeWrap = document.createElement("div");
  treeWrap.className = "tree-wrap";
  section.appendChild(treeWrap);

  renderTree(treeWrap, taxon);

  return section;
}

/* ---------------------------------------------------------------
   ORGANISM — the record, its barcode motif, and molecular evidence
   --------------------------------------------------------------- */

/**
 * ORGANISM — what was found: names, rank, identifier, and why it matched.
 *
 * Holds taxonomy only. Sequence data lives in its own section below, so the
 * two can evolve separately as the backend grows.
 */
function buildOrganismSection(taxon, uid) {
  const section = document.createElement("section");
  section.className = "organism-section";
  const headingId = `${uid}-organism-heading`;
  section.setAttribute("aria-labelledby", headingId);

  section.appendChild(buildPlateHead(taxon, headingId));

  return section;
}

/**
 * COMPARISON — how this organism relates to another.
 *
 * Sits after the lineage because it asks a question about that lineage,
 * and before the sequence data, which is about this organism alone.
 */
function buildComparisonSection(taxon) {
  const host = document.createDocumentFragment();
  const section = renderCompare(host, taxon);
  return section;
}

/**
 * SCIENTIFIC DATA — the measurements behind the record.
 *
 * Today that is the COX1 barcode read and the GenBank records backing it.
 * Fossil occurrences, geological dates and cross-database links would each
 * be another block appended here, fed by their own endpoint; nothing above
 * this function needs to know about them.
 */
function buildScientificDataSection(taxon, uid) {
  const section = document.createElement("section");
  section.className = "science-data-section";
  const headingId = `${uid}-data-heading`;
  section.setAttribute("aria-labelledby", headingId);

  section.appendChild(buildSectionHeading("Scientific data", headingId));

  const barcodeEl = document.createElement("div");
  barcodeEl.className = "barcode";
  section.appendChild(barcodeEl);
  renderBarcode(barcodeEl, taxon.taxid);

  section.appendChild(buildEvidence(taxon));

  return section;
}

function buildPlateHead(taxon, headingId) {
  const header = document.createElement("header");
  header.className = "plate-head";

  if (taxon.kingdom) {
    const kingdom = document.createElement("p");
    kingdom.className = "plate-kingdom mono";
    kingdom.textContent = taxon.kingdom;
    header.appendChild(kingdom);
  }

  const hasCommon = Boolean(taxon.common_name);
  const headline = document.createElement("h3");
  headline.id = headingId;
  headline.className = hasCommon ? "plate-name" : "plate-name plate-name--sci";
  headline.textContent = hasCommon ? taxon.common_name : taxon.scientific_name;
  header.appendChild(headline);

  if (hasCommon) {
    const sci = document.createElement("p");
    sci.className = "plate-sciname";
    sci.textContent = taxon.scientific_name;
    header.appendChild(sci);
  }

  const dl = document.createElement("dl");
  dl.className = "plate-facts";
  dl.appendChild(buildFact("Rank", taxon.rank, { mono: true }));
  dl.appendChild(buildFact("TaxID", taxon.taxid, { mono: true }));
  dl.appendChild(buildFact("Division", taxon.division));
  dl.appendChild(buildFact("Genetic code", taxon.genetic_code));
  dl.appendChild(buildFact("Other names", (taxon.other_names || []).join(", ")));
  dl.appendChild(buildMatchFact(taxon));
  header.appendChild(dl);

  return header;
}

function buildFact(label, value, { mono = false } = {}) {
  const wrap = document.createElement("div");
  wrap.className = "fact";

  const dt = document.createElement("dt");
  dt.textContent = label;
  wrap.appendChild(dt);

  const dd = document.createElement("dd");
  const isBlank = !value;
  dd.textContent = isBlank ? "Not recorded" : value;
  if (isBlank) dd.classList.add("is-blank");
  if (mono && !isBlank) dd.classList.add("mono");
  wrap.appendChild(dd);

  return wrap;
}

function buildMatchFact(taxon) {
  const wrap = document.createElement("div");
  wrap.className = "fact";

  const dt = document.createElement("dt");
  dt.textContent = "Matched via";
  wrap.appendChild(dt);

  const dd = document.createElement("dd");
  const isBlank = !taxon.match_reason;
  dd.textContent = isBlank ? "Not recorded" : taxon.match_reason;
  if (isBlank) dd.classList.add("is-blank");

  if (!isBlank && taxon.source === "gbif-resolved") {
    dd.appendChild(document.createTextNode(" "));
    const note = document.createElement("span");
    note.className = "source-note";
    note.textContent = "(everyday name via GBIF; taxonomy from NCBI)";
    dd.appendChild(note);
  }

  wrap.appendChild(dd);
  return wrap;
}

/* ---------------------------------------------------------------
   Molecular evidence
   --------------------------------------------------------------- */

let evidenceIdCounter = 0;

function buildEvidence(taxon) {
  const section = document.createElement("div");
  section.className = "evidence";

  const heading = document.createElement("h4");
  heading.className = "evidence-heading";

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "evidence-toggle";
  toggle.setAttribute("aria-expanded", "false");

  const panelId = `evidence-panel-${++evidenceIdCounter}`;
  toggle.setAttribute("aria-controls", panelId);

  const mark = document.createElement("span");
  mark.className = "evidence-toggle-mark";
  mark.setAttribute("aria-hidden", "true");
  toggle.appendChild(mark);
  toggle.appendChild(document.createTextNode("Molecular evidence — COX1 records"));

  heading.appendChild(toggle);
  section.appendChild(heading);

  const panel = document.createElement("div");
  panel.className = "evidence-panel";
  panel.id = panelId;
  panel.hidden = true;
  section.appendChild(panel);

  let loaded = false;

  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    panel.hidden = expanded;
    if (!expanded && !loaded) {
      // Only remember a load that worked. Marking it done before the request
      // resolves leaves a failed fetch permanently stuck on its error, with
      // closing and reopening the panel doing nothing.
      loadEvidence(panel, taxon.taxid).then((ok) => {
        loaded = ok;
      });
    }
  });

  return section;
}

async function loadEvidence(panel, taxid) {
  clearNode(panel);

  const intro = document.createElement("p");
  intro.className = "evidence-intro";
  intro.textContent =
    "COX1 is the mitochondrial gene commonly used to fingerprint species — a DNA barcode held in GenBank.";
  panel.appendChild(intro);

  const status = document.createElement("p");
  status.className = "evidence-loading";
  status.textContent = "Fetching COX1 records…";
  panel.appendChild(status);

  let response;
  try {
    response = await fetchSequences(taxid);
  } catch (error) {
    status.remove();
    const message = document.createElement("p");
    message.className = "evidence-empty";
    message.textContent =
      error instanceof ApiError && error.kind === "offline"
        ? "Couldn't reach the server to fetch COX1 records. Close and reopen this panel to try again."
        : "COX1 records couldn't be loaded right now. Close and reopen this panel to try again.";
    panel.appendChild(message);
    return false;
  }

  status.remove();

  if (!response.available || response.sequences.length === 0) {
    const empty = document.createElement("p");
    empty.className = "evidence-empty";
    empty.textContent = "NCBI holds no confirmed COX1 barcode records for this organism.";
    panel.appendChild(empty);
    return true;
  }

  const list = document.createElement("ul");
  list.className = "sequence-list";

  response.sequences.forEach((seq) => {
    const li = document.createElement("li");
    li.className = "sequence-item";

    const accession = document.createElement("span");
    accession.className = "sequence-accession mono";
    accession.textContent = seq.accession;
    li.appendChild(accession);

    const title = document.createElement("span");
    title.className = "sequence-title";
    title.textContent = seq.title;
    li.appendChild(title);

    const length = document.createElement("span");
    length.className = "sequence-length mono";
    length.textContent = `${seq.length.toLocaleString()} bp`;
    li.appendChild(length);

    const completeness = document.createElement("span");
    completeness.className = seq.complete
      ? "sequence-completeness is-complete"
      : "sequence-completeness";
    completeness.textContent = seq.complete ? "Complete cds" : "Partial cds";
    li.appendChild(completeness);

    list.appendChild(li);
  });

  panel.appendChild(list);

  const count = document.createElement("p");
  count.className = "evidence-count";
  // `count` is how many confirmed records the search found, not everything
  // NCBI holds — the query pool is capped and non-COX1 hits are filtered out.
  count.textContent =
    response.count > response.sequences.length
      ? `Showing ${response.sequences.length} of ${response.count.toLocaleString()} confirmed ${response.gene} records found.`
      : `${response.sequences.length} confirmed ${response.gene} record${
          response.sequences.length === 1 ? "" : "s"
        } found.`;
  panel.appendChild(count);

  return true;
}

/* ---------------------------------------------------------------
   Utilities
   --------------------------------------------------------------- */

function clearNode(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}
