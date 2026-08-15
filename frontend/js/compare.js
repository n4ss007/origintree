/**
 * "How closely related are these two?"
 *
 * The rest of the site answers questions about one organism. This answers
 * the one a database cannot: given two, how much of their classification is
 * the same, and where does it stop being the same?
 *
 * The drawing reuses the lineage tree's grammar — a green path, gold at the
 * point that matters — so a comparison reads as the same kind of object as
 * a lineage rather than a separate widget.
 */

import { compareOrganisms, compareBarcodes, ApiError } from "./api.js";
import { createLoader } from "./loader.js";

const SVG_NS = "http://www.w3.org/2000/svg";

/** How many of the shared steps to name. The rest are counted, not listed. */
const SHARED_TAIL = 3;

let uidCounter = 0;

/**
 * Renders the compare control for `taxon` into `container`.
 *
 * @param {HTMLElement} container
 * @param {import("./types.js").Taxon} taxon  the organism already on screen
 */
export function renderCompare(container, taxon) {
  const uid = `cmp-${++uidCounter}`;
  const section = document.createElement("section");
  section.className = "compare-section";
  section.setAttribute("aria-labelledby", `${uid}-heading`);

  const heading = document.createElement("h3");
  heading.id = `${uid}-heading`;
  heading.className = "section-heading";
  heading.textContent = "Compare with another organism";
  section.appendChild(heading);

  const intro = document.createElement("p");
  intro.className = "compare-intro";
  const subject = taxon.common_name || taxon.scientific_name;
  intro.textContent = `See how much of its classification ${subject} shares with something else, and where the two part.`;
  section.appendChild(intro);

  const form = document.createElement("form");
  form.className = "compare-form";
  form.noValidate = true;

  const label = document.createElement("label");
  label.className = "visually-hidden";
  label.htmlFor = `${uid}-input`;
  label.textContent = "Organism to compare with";
  form.appendChild(label);

  const field = document.createElement("div");
  field.className = "compare-field";

  const input = document.createElement("input");
  input.type = "text";
  input.id = `${uid}-input`;
  input.className = "compare-input";
  input.placeholder = "Common or scientific name…";
  input.autocomplete = "off";
  input.spellcheck = false;
  field.appendChild(input);

  const button = document.createElement("button");
  button.type = "submit";
  button.className = "compare-button";
  button.textContent = "Compare";
  field.appendChild(button);

  form.appendChild(field);
  section.appendChild(form);

  const suggestions = buildSuggestions(taxon, (name) => {
    input.value = name;
    run(name);
  });
  if (suggestions) section.appendChild(suggestions);

  const output = document.createElement("div");
  output.className = "compare-output";
  output.setAttribute("aria-live", "polite");
  section.appendChild(output);

  let requestId = 0;
  let loader = null;

  function stopLoader() {
    if (loader) {
      loader.stop();
      loader = null;
    }
  }

  async function run(term) {
    const trimmed = (term || "").trim();
    if (!trimmed) {
      input.focus();
      return;
    }

    const id = ++requestId;
    button.disabled = true;
    button.textContent = "Comparing…";
    stopLoader();
    clearNode(output);
    loader = createLoader("Tracing both lineages…");
    output.appendChild(loader.el);

    let result;
    try {
      // the organism on screen is passed by TaxID, which is exact and
      // avoids re-running a search that has already been resolved
      result = await compareOrganisms(taxon.taxid, trimmed);
    } catch (error) {
      if (id !== requestId) return;
      stopLoader();
      resetButton();
      renderMessage(output, messageFor(error), "compare-error");
      return;
    }

    if (id !== requestId) return;
    stopLoader();
    resetButton();
    renderResult(output, result, taxon);
  }

  function resetButton() {
    button.disabled = false;
    button.textContent = "Compare";
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    run(input.value);
  });

  container.appendChild(section);
  return section;
}

function messageFor(error) {
  if (error instanceof ApiError && error.kind === "offline") {
    return "Couldn't reach the server to compare.";
  }
  return (error && error.message) || "That comparison could not be completed.";
}

/* ---------------------------------------------------------------
   Suggestions — a way in for someone who has no second organism in mind
   --------------------------------------------------------------- */

const STARTERS = ["human", "octopus", "giant panda", "king cobra"];

function buildSuggestions(taxon, onPick) {
  const own = (taxon.common_name || taxon.scientific_name || "").toLowerCase();
  const options = STARTERS.filter((name) => name !== own).slice(0, 3);

  if (!options.length) return null;

  const wrap = document.createElement("div");
  wrap.className = "compare-suggestions";

  const label = document.createElement("span");
  label.className = "compare-suggestions-label";
  label.textContent = "or try";
  wrap.appendChild(label);

  options.forEach((name) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "compare-chip";
    chip.textContent = name;
    chip.addEventListener("click", () => onPick(name));
    wrap.appendChild(chip);
  });

  return wrap;
}

/* ---------------------------------------------------------------
   Result
   --------------------------------------------------------------- */

function renderMessage(container, text, className) {
  clearNode(container);
  const p = document.createElement("p");
  p.className = className;
  p.textContent = text;
  container.appendChild(p);
}

function renderResult(container, result, subject) {
  clearNode(container);

  const summary = document.createElement("p");
  summary.className = "compare-summary";
  summary.textContent = result.summary;
  container.appendChild(summary);

  if (result.common_ancestor) {
    container.appendChild(buildDivergence(result));
  }

  if (result.fossil) {
    container.appendChild(buildFossil(result.fossil));
  }

  // Molecular evidence is a second, slower round trip, so it is offered
  // rather than fetched: the classification answer arrives first.
  if (result.relationship === "distinct" && result.a && result.b) {
    container.appendChild(buildBarcodePanel(result.a, result.b));
  }

  // reveal on the next frame so the drawing animates in rather than
  // appearing fully formed
  window.requestAnimationFrame(() => container.classList.add("is-in"));
}

/**
 * The shared path, the point it stops being shared, and the two organisms.
 *
 * Only the last few shared steps are named. Listing all twenty-seven would
 * bury the one row that answers the question.
 */
function buildDivergence(result) {
  const figure = document.createElement("div");
  figure.className = "divergence";

  const shared = result.shared || [];
  const hidden = Math.max(0, shared.length - SHARED_TAIL);
  const tail = shared.slice(-SHARED_TAIL);

  if (hidden > 0) {
    figure.appendChild(
      buildRow(`${hidden} earlier shared ranks`, "", "divergence-row is-elided")
    );
  }

  tail.forEach((step, index) => {
    const isSplit = index === tail.length - 1;
    figure.appendChild(
      buildRow(
        step.name,
        step.rank,
        `divergence-row${isSplit ? " is-split" : " is-shared"}`
      )
    );
  });

  figure.appendChild(buildBranches(result));

  return figure;
}

function buildRow(name, rank, className) {
  const row = document.createElement("div");
  row.className = className;

  const mark = document.createElementNS(SVG_NS, "svg");
  mark.setAttribute("class", "divergence-mark");
  mark.setAttribute("viewBox", "0 0 12 12");
  mark.setAttribute("width", "12");
  mark.setAttribute("height", "12");
  mark.setAttribute("aria-hidden", "true");
  const dot = document.createElementNS(SVG_NS, "circle");
  dot.setAttribute("cx", "6");
  dot.setAttribute("cy", "6");
  dot.setAttribute("r", "3.4");
  mark.appendChild(dot);
  row.appendChild(mark);

  const text = document.createElement("span");
  text.className = "divergence-name";
  text.textContent = name;
  row.appendChild(text);

  if (rank) {
    const rankEl = document.createElement("span");
    rankEl.className = "divergence-rank mono";
    rankEl.textContent = rank;
    row.appendChild(rankEl);
  }

  return row;
}

/** The two paths after the split, side by side. */
function buildBranches(result) {
  const wrap = document.createElement("div");
  wrap.className = "divergence-branches";

  wrap.appendChild(buildBranch(result.a, result.only_a, "a"));
  wrap.appendChild(buildBranch(result.b, result.only_b, "b"));

  return wrap;
}

function buildBranch(taxon, steps, side) {
  const branch = document.createElement("div");
  branch.className = `divergence-branch is-${side}`;

  const name = document.createElement("p");
  name.className = "divergence-branch-name";
  name.textContent = taxon.common_name || taxon.scientific_name;
  branch.appendChild(name);

  const sci = document.createElement("p");
  sci.className = "divergence-branch-sci";
  sci.textContent = taxon.scientific_name;
  branch.appendChild(sci);

  const count = document.createElement("p");
  count.className = "divergence-branch-count mono";
  const n = (steps || []).length;
  count.textContent = n === 0 ? "no further steps" : `${n} further ${n === 1 ? "step" : "steps"}`;
  branch.appendChild(count);

  if (n) {
    const list = document.createElement("ol");
    list.className = "divergence-steps";

    (steps || []).forEach((step) => {
      const li = document.createElement("li");

      const stepName = document.createElement("span");
      stepName.className = "divergence-step-name";
      stepName.textContent = step.name;
      li.appendChild(stepName);

      if (step.rank && step.rank !== "no rank") {
        const stepRank = document.createElement("span");
        stepRank.className = "divergence-step-rank mono";
        stepRank.textContent = step.rank;
        li.appendChild(stepRank);
      }

      list.appendChild(li);
    });

    branch.appendChild(list);
  }

  return branch;
}

/**
 * A dated fossil for the clade the two organisms share.
 *
 * Worded as a minimum age for the clade, which is what a fossil gives you —
 * not the date these two lineages separated. Only shown when the project's
 * dataset actually holds a row for that clade.
 */
function buildFossil(fossil) {
  const note = document.createElement("div");
  note.className = "fossil-note";

  const label = document.createElement("p");
  label.className = "fossil-label mono";
  label.textContent = "Fossil evidence";
  note.appendChild(label);

  const age = document.createElement("p");
  age.className = "fossil-age";
  const min = fossil.minimum_ma;
  const max = fossil.maximum_ma;
  const range =
    min != null && max != null ? `${min}–${max} million years ago` : "an undated horizon";
  age.textContent = `The oldest known fossil assigned to ${fossil.clade} dates to ${range}, so the group is at least that old.`;
  note.appendChild(age);

  if (fossil.justification) {
    const why = document.createElement("p");
    why.className = "fossil-justification";
    why.textContent = fossil.justification;
    note.appendChild(why);
  }

  if (fossil.source) {
    const source = document.createElement("p");
    source.className = "fossil-source";
    source.textContent = fossil.source;
    note.appendChild(source);
  }

  return note;
}

/* ---------------------------------------------------------------
   Molecular comparison — how much the two barcodes actually agree
   --------------------------------------------------------------- */

/**
 * The classification answer says where two organisms are filed. This says
 * how far their DNA has actually drifted apart, which is the other half of
 * the question and the part a database makes you run BLAST for.
 */
function buildBarcodePanel(taxonA, taxonB) {
  const panel = document.createElement("div");
  panel.className = "barcode-compare";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "barcode-compare-toggle";
  button.textContent = "Compare their DNA barcodes";
  panel.appendChild(button);

  const output = document.createElement("div");
  output.className = "barcode-compare-output";
  output.setAttribute("aria-live", "polite");
  panel.appendChild(output);

  let loaded = false;
  let loader = null;

  button.addEventListener("click", async () => {
    if (loaded) return;

    button.disabled = true;
    loader = createLoader("Aligning COX1 records…");
    clearNode(output);
    output.appendChild(loader.el);

    let result;
    try {
      result = await compareBarcodes(taxonA.taxid, taxonB.taxid);
    } catch (error) {
      loader.stop();
      button.disabled = false;
      renderMessage(output, messageFor(error), "compare-error");
      return;
    }

    loader.stop();
    loaded = true;
    button.remove();
    renderBarcodeResult(output, result, taxonA, taxonB);
  });

  return panel;
}

function renderBarcodeResult(container, result, taxonA, taxonB) {
  clearNode(container);

  if (!result.available) {
    renderMessage(container, result.reason || "No comparable records are held.", "compare-status");
    return;
  }

  const headline = document.createElement("p");
  headline.className = "barcode-identity";

  const figure = document.createElement("strong");
  figure.textContent = `${result.identity}%`;
  headline.appendChild(figure);
  headline.append(
    ` of their ${result.gene} barcode matches, over ${result.aligned_length} aligned bases.`
  );
  container.appendChild(headline);

  const detail = document.createElement("p");
  detail.className = "barcode-detail";
  detail.textContent =
    `${result.matches} bases agree and ${result.differences} differ. ` +
    "COX1 is the standard animal barcoding gene: closely related species " +
    "read high here, distant ones lower.";
  container.appendChild(detail);

  const bar = document.createElement("div");
  bar.className = "identity-bar";
  bar.setAttribute("role", "img");
  bar.setAttribute(
    "aria-label",
    `${result.identity} percent of aligned bases match`
  );
  const fill = document.createElement("span");
  fill.className = "identity-bar-fill";
  bar.appendChild(fill);
  container.appendChild(bar);
  // width set after insertion so the bar grows into place
  window.requestAnimationFrame(() => {
    fill.style.width = `${Math.max(0, Math.min(100, result.identity))}%`;
  });

  const sources = document.createElement("p");
  sources.className = "barcode-sources mono";
  const nameA = taxonA.common_name || taxonA.scientific_name;
  const nameB = taxonB.common_name || taxonB.scientific_name;
  sources.textContent =
    `${nameA} ${result.a.accession} · ${nameB} ${result.b.accession}`;
  container.appendChild(sources);
}

function clearNode(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}
