/**
 * The only module that talks to the network.
 *
 * Views never call fetch directly, so there is one place to change when the
 * API moves and one place that decides what a failure means.
 */

import { API_BASE, RESULT_LIMIT, SEQUENCE_LIMIT } from "./config.js";

/**
 * A failure the interface can act on.
 *
 * `kind` is "offline" when the server could not be reached at all, which
 * needs a different message from a request the server understood and
 * refused.
 */
export class ApiError extends Error {
  constructor(message, kind) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
  }
}

async function request(path) {
  let response;

  try {
    response = await fetch(API_BASE + path);
  } catch {
    // fetch only rejects for network-level failures, which is exactly what a
    // server that was never started looks like.
    throw new ApiError("Could not reach the OriginTree server.", "offline");
  }

  let body;

  try {
    body = await response.json();
  } catch {
    throw new ApiError("The server sent back something unreadable.", "parse");
  }

  if (!response.ok) {
    throw new ApiError(body.detail || "That search could not be completed.", "http");
  }

  return body;
}

/**
 * Search NCBI Taxonomy.
 *
 * @param   {string} term
 * @param   {number} [limit]
 * @returns {Promise<import("./types.js").SearchResponse>}
 */
export function searchTaxa(term, limit = RESULT_LIMIT) {
  const query = `animal=${encodeURIComponent(term)}&limit=${limit}`;
  return request(`/api/search?${query}`);
}

/**
 * COX1 records held for a taxon. Slow, so it is only called on demand.
 *
 * @param   {string} taxid
 * @param   {number} [limit]
 * @returns {Promise<import("./types.js").SequenceResponse>}
 */
export function fetchSequences(taxid, limit = SEQUENCE_LIMIT) {
  return request(`/api/species/${encodeURIComponent(taxid)}/sequences?limit=${limit}`);
}

/**
 * An 8-base read from a taxon's best COX1 record, straight from GenBank.
 *
 * @param   {string} taxid
 * @returns {Promise<import("./types.js").BarcodeWindow>}
 */
export function fetchBarcode(taxid) {
  return request(`/api/species/${encodeURIComponent(taxid)}/barcode`);
}
