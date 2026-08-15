/**
 * Where the API lives.
 *
 * OriginTree is a static site with no build step, so there is no compile-time
 * environment to read. These are the static-site equivalents, in priority
 * order, and they mean the address is written down in exactly one place
 * rather than scattered through the modules that call it.
 *
 *   1. window.ORIGINTREE_API_BASE   set by a deploy script or inline snippet
 *   2. <meta name="origintree-api-base" content="https://api.example.org">
 *   3. same origin                  the normal case: the API serves this page
 *   4. local development            only when opened straight off disk
 */

const DEV_API_BASE = "http://127.0.0.1:8000";

function fromGlobal() {
  return typeof window.ORIGINTREE_API_BASE === "string"
    ? window.ORIGINTREE_API_BASE.trim()
    : "";
}

function fromMetaTag() {
  const tag = document.querySelector('meta[name="origintree-api-base"]');
  return tag ? tag.content.trim() : "";
}

function resolveApiBase() {
  const configured = fromGlobal() || fromMetaTag();

  if (configured) {
    return configured.replace(/\/$/, "");
  }

  // Opened by double-clicking index.html: there is no server at this origin.
  if (window.location.protocol === "file:") {
    return DEV_API_BASE;
  }

  return "";
}

export const API_BASE = resolveApiBase();

/** How many matches to ask for. More than a handful stops being a choice. */
export const RESULT_LIMIT = 6;

/** How many COX1 records to list in the molecular evidence panel. */
export const SEQUENCE_LIMIT = 6;

/** Milliseconds between one lineage step appearing and the next. */
export const TREE_STEP_MS = 180;
