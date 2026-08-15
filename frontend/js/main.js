/**
 * Wires the search panel to the results region and owns the app's state: the
 * last query run, the response it got back, and which of the matches is
 * currently selected. Every other module is a pure renderer that this file
 * calls with fresh state — nothing else touches #results directly.
 *
 * Also starts the hero's opening sequence and registers the two static
 * sections (science, footer) for the same scroll-reveal the dynamic result
 * sections use.
 */

import { searchTaxa, ApiError } from "./api.js";
import { initSearch } from "./search.js";
import { renderLoading, renderError, renderEmpty, renderResults, registerReveal } from "./results.js";
import { initHero } from "./hero.js";

const heroEl = document.getElementById("hero");
const searchPanel = document.getElementById("searchPanel");
const resultsEl = document.getElementById("results");
const scienceEl = document.getElementById("science");
const footerEl = document.querySelector(".site-footer");

initHero(heroEl);

if (scienceEl) registerReveal(scienceEl);
if (footerEl) registerReveal(footerEl);

let requestId = 0;
let currentResponse = null;
let selectedIndex = 0;

/**
 * Landing or exploring.
 *
 * The introductory copy belongs to the landing state only. Once someone has
 * searched they are reading a record, and making them scroll past the same
 * explanation under every result turns the page into a brochure.
 */
function setView(view) {
  document.body.dataset.view = view;
}

setView("landing");

const search = initSearch(searchPanel, { onSubmit: submit });

async function submit(term) {
  const id = ++requestId;

  search.setBusy(true);
  setView("exploring");
  transition(() => renderLoading(resultsEl, term));

  // The hero fills the viewport, so results arrive entirely below the fold.
  // Without this the page looks like it ignored the search. Moving to the
  // "Tracing lineage…" state right away also makes the wait legible.
  revealResults();

  let response;
  try {
    response = await searchTaxa(term);
  } catch (error) {
    if (id !== requestId) return;
    search.setBusy(false);
    transition(() => renderError(resultsEl, toApiError(error), { onRetry: () => submit(term) }));
    return;
  }

  if (id !== requestId) return;
  search.setBusy(false);

  currentResponse = response;
  selectedIndex = 0;

  if (!response.results || response.results.length === 0) {
    transition(() => renderEmpty(resultsEl, response.query || term));
    return;
  }

  transition(() => renderResults(resultsEl, currentResponse, { selectedIndex, onSelect: select }));
}

function select(index) {
  if (!currentResponse) return;
  selectedIndex = index;
  transition(() => renderResults(resultsEl, currentResponse, { selectedIndex, onSelect: select }));
}

/** Bring the results region to the top of the viewport.
 *
 *  Only ever scrolls down to it: if the reader has already scrolled past the
 *  hero and is reading a result, yanking the page back up would be worse
 *  than leaving it alone. */
function revealResults() {
  const top = resultsEl.getBoundingClientRect().top + window.scrollY;

  if (window.scrollY >= top - 8) {
    return;
  }

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  window.scrollTo({
    top: top - 24,
    behavior: reduced ? "auto" : "smooth",
  });
}

/** A short cross-fade around every state change, so a second search — or a
 *  different pick from a set of matches — settles into place rather than
 *  snapping. */
function transition(paint) {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced) {
    paint();
    return;
  }
  resultsEl.classList.add("is-swapping");
  window.setTimeout(() => {
    paint();
    resultsEl.classList.remove("is-swapping");
  }, 150);
}

function toApiError(error) {
  return error instanceof ApiError ? error : new ApiError("Something went wrong.", "http");
}
