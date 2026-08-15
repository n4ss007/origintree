/**
 * The 8-base barcode strip: a short, real read from a taxon's COX1 record,
 * shown as a supporting motif beside the organism's record rather than as
 * a feature in its own right.
 *
 * The eight letters rendered here are exactly what `/barcode` returned —
 * this module has no path that invents, pads, reorders, or substitutes a
 * base. When the record isn't available, it says so and stops; it never
 * fills the strip with placeholder letters to keep the layout busy.
 */

import { fetchBarcode, ApiError } from "./api.js";

const REVEAL_STEP_MS = 110;

/** Renders the barcode strip for `taxid` into `container`. */
export async function renderBarcode(container, taxid) {
  clearNode(container);
  container.classList.add("is-loading");

  let response;
  try {
    response = await fetchBarcode(taxid);
  } catch (error) {
    container.classList.remove("is-loading");
    if (error instanceof ApiError && error.kind === "offline") {
      // The record panel above already explains the server is down; this
      // motif just stays quiet rather than repeating it.
      return;
    }
    return;
  }

  container.classList.remove("is-loading");

  if (!response.available || !response.bases) {
    const empty = document.createElement("p");
    empty.className = "barcode-empty";
    empty.textContent = "No confirmed COX1 record for this organism.";
    container.appendChild(empty);
    return;
  }

  const bases = response.bases;

  const label = document.createElement("p");
  label.className = "barcode-label mono";
  label.textContent = "DNA barcode — COX1";
  container.appendChild(label);

  const strip = document.createElement("div");
  strip.className = "barcode-strip";
  strip.setAttribute("role", "text");

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  Array.from(bases).forEach((base, i) => {
    const cell = document.createElement("span");
    cell.className = "barcode-base mono";
    cell.textContent = base;
    if (!reduceMotion) {
      cell.style.transitionDelay = `${i * REVEAL_STEP_MS}ms`;
    }
    strip.appendChild(cell);
  });

  container.appendChild(strip);

  const credit = document.createElement("p");
  credit.className = "barcode-credit mono";
  const start = response.offset + 1;
  const end = response.offset + bases.length;
  credit.textContent = `${response.accession} · ${response.gene} · bases ${start}–${end}`;
  container.appendChild(credit);

  if (reduceMotion) {
    strip.querySelectorAll(".barcode-base").forEach((cell) => cell.classList.add("is-in"));
    return;
  }

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      strip.querySelectorAll(".barcode-base").forEach((cell) => cell.classList.add("is-in"));
    });
  });
}

function clearNode(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}
