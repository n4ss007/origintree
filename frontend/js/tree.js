/**
 * The lineage tree: inline SVG, generated fresh for whichever taxon is
 * showing.
 *
 * The path from the root of the record down to the organism is drawn as a
 * genuine cascade — every step bends the path left or right by a different
 * amount, so the shape itself reads as a sequence of branch points rather
 * than a straight rod with stubs pinned to it. Major, unlabelled ranks
 * still branch off the record but never show unless the reader opens
 * "show all steps" — the branch point closest to the reader is not, on its
 * own, a claim about what's on the other end.
 *
 * Every step carries its name and rank. The ranks people are taught are set
 * larger and darker; the unnamed clades between them, which only appear
 * once the full lineage is opened, are set smaller and lighter so the
 * familiar chain still leads the eye through 25–30 steps. Hover or keyboard
 * focus puts any step's full record in the reading beneath the diagram.
 *
 * The tree is never given its own scrollbar. However long the lineage, it
 * is drawn at full height and the page scrolls to it — a diagram boxed
 * inside its own scroll container hides most of itself.
 *
 * A screen reader gets the same lineage a different way: a genuine <ol>
 * holding every step, always in full, regardless of what the diagram is
 * currently showing.
 */

import { TREE_STEP_MS } from "./config.js";

let instanceCounter = 0;

/** Renders (or re-renders) the lineage tree for `taxon` into `container`. */
export function renderTree(container, taxon) {
  clearNode(container);

  const uid = `tree-${++instanceCounter}`;
  const state = {
    taxon,
    showFull: false,
  };

  const canvas = document.createElement("div");
  canvas.className = "tree-canvas";
  container.appendChild(canvas);

  const inspector = buildInspector(uid);
  container.appendChild(inspector.el);

  const rawLineage = taxon.lineage || [];
  const hasMinor = rawLineage.some((node) => !node.major);

  let toggle = null;
  if (hasMinor) {
    toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "tree-toggle";
    container.appendChild(toggle);
    toggle.addEventListener("click", () => {
      state.showFull = !state.showFull;
      draw(canvas, taxon, state.showFull, uid, inspector, { animate: false });
      updateToggleLabel(toggle, taxon, state.showFull);
    });
    updateToggleLabel(toggle, taxon, state.showFull);
  }

  const list = buildAccessibleList(taxon, uid);
  container.appendChild(list);

  // Draw from the measured width, and wait for one. The card is often still
  // detached when this runs, and a zero-width measurement would fall back to
  // the minimum, producing a viewBox far taller than it is wide that then
  // stretches to a ridiculous height once it is placed on the page.
  let lastWidth = 0;

  const observer = new ResizeObserver((entries) => {
    if (!canvas.isConnected) {
      observer.disconnect();
      return;
    }

    const width = Math.round(entries[0].contentRect.width);

    if (width === 0 || Math.abs(width - lastWidth) < 8) {
      return;
    }

    const isFirstDraw = lastWidth === 0;
    lastWidth = width;

    draw(canvas, taxon, state.showFull, uid, inspector, { animate: isFirstDraw });
  });

  observer.observe(canvas);
}

function updateToggleLabel(toggle, taxon, showFull) {
  const total = (taxon.lineage || []).length + 1;
  const majorCount = (taxon.lineage || []).filter((n) => n.major).length + 1;
  toggle.textContent = showFull
    ? `Show key ranks only (${majorCount})`
    : `Show all ${total} steps`;
  toggle.setAttribute("aria-expanded", String(showFull));
}

/* ---------------------------------------------------------------
   Layout
   --------------------------------------------------------------- */

const ROW_H = 78;
// Tighter than ROW_H (dense mode can mean 25-30 rows) but still tall enough
// to clear a wrapped major-node label without touching the row below it.
const ROW_H_DENSE = 54;
const TOP_PAD = 36;
// Generous enough to clear the terminal node's rank + rule even when its
// name wraps to a second line (see WRAP_LINE_OFFSET).
const BOTTOM_PAD = 76;
const COMPACT_BREAK = 480;
const DENSE_ROW_THRESHOLD = 14;

// A repeating, non-uniform sequence of side/weight multipliers. Using a
// fixed cycle rather than plain alternation keeps the cascade legible
// (deterministic, testable) while avoiding the metronome look of a
// straight trunk with evenly-spaced stubs either side of it.
const JOG_CYCLE = [1, -0.72, 0.55, -1, 0.4, -0.6];

function computeNodes(taxon, showFull) {
  const raw = taxon.lineage || [];
  const source = showFull ? raw : raw.filter((n) => n.major);

  const entries = source.map((n) => ({
    name: n.name,
    rank: n.rank,
    taxid: n.taxid,
    major: n.major,
    terminal: false,
  }));

  entries.push({
    name: taxon.scientific_name,
    rank: taxon.rank,
    taxid: taxon.taxid,
    major: true,
    terminal: true,
  });

  return entries;
}

function layout(entries, width, dense) {
  const w = Math.max(width, 260);
  const compact = w < COMPACT_BREAK;
  const centerX = w / 2;
  const rowH = dense ? ROW_H_DENSE : ROW_H;
  const jogBase = compact
    ? clamp(16, w * 0.1, 46)
    : clamp(30, w * 0.15, 130);
  const lastIndex = entries.length - 1;

  const nodes = entries.map((entry, i) => {
    const y = TOP_PAD + i * rowH;
    if (i === lastIndex) {
      return { ...entry, x: centerX, y, side: 0 };
    }
    const mult = JOG_CYCLE[i % JOG_CYCLE.length];
    const x = centerX + mult * jogBase;
    return { ...entry, x, y, side: mult >= 0 ? 1 : -1 };
  });

  const height = TOP_PAD + lastIndex * rowH + BOTTOM_PAD;
  return { nodes, width: w, height, centerX, compact };
}

function clamp(min, value, max) {
  return Math.min(max, Math.max(min, value));
}

/* ---------------------------------------------------------------
   Drawing
   --------------------------------------------------------------- */

const SVG_NS = "http://www.w3.org/2000/svg";

function draw(canvas, taxon, showFull, uid, inspector, { animate, attempt = 0 }) {
  const measured = canvas.getBoundingClientRect().width;

  if (measured === 0 && attempt < 20) {
    window.requestAnimationFrame(() => {
      draw(canvas, taxon, showFull, uid, inspector, { animate, attempt: attempt + 1 });
    });
    return;
  }

  const entries = computeNodes(taxon, showFull);
  // A long lineage gets tighter rows so it stays a readable diagram rather
  // than a very tall one. It is never given its own scrollbar — the page
  // scrolls, and the whole tree is drawn.
  const dense = entries.length > DENSE_ROW_THRESHOLD;
  const { nodes, width, height, centerX, compact } = layout(entries, measured, dense);

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const willAnimate = animate && !reduceMotion;

  const previousSvg = canvas.querySelector(".tree-svg");
  if (previousSvg) {
    previousSvg.classList.add("is-swapping");
  }

  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "tree-svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-labelledby", `${uid}-title`);
  svg.setAttribute("aria-describedby", `${uid}-desc`);

  const title = document.createElementNS(SVG_NS, "title");
  title.id = `${uid}-title`;
  const displayName = taxon.common_name || taxon.scientific_name;
  title.textContent = `Lineage of ${displayName}`;
  svg.appendChild(title);

  const desc = document.createElementNS(SVG_NS, "desc");
  desc.id = `${uid}-desc`;
  desc.textContent = `A branching diagram running from ${nodes[0]?.name || "the root of the record"} down to ${displayName}, showing ${nodes.length} named steps. The full reading is also listed below as text.`;
  svg.appendChild(desc);

  svg.appendChild(buildMarkDefs(uid));

  const buildElements = [];
  let prev = null;

  nodes.forEach((node, i) => {
    let seg = null;

    if (prev) {
      seg = document.createElementNS(SVG_NS, "path");
      seg.setAttribute(
        "class",
        `lineage-seg${node.major ? "" : " is-minor"}`
      );
      const cx = (prev.x + node.x) / 2;
      const cy = prev.y + (node.y - prev.y) * 0.32;
      seg.setAttribute("d", `M ${prev.x} ${prev.y} Q ${cx} ${cy} ${node.x} ${node.y}`);
      svg.appendChild(seg);
    }

    // A short, unlabelled stub at every non-terminal major branch point —
    // this diagram is one path excerpted from a much larger tree, and the
    // stub says so without inventing what is on the other end of it.
    if (!node.terminal && node.major) {
      svg.appendChild(buildStub(node, centerX));
    }

    const { positioned, animated } = buildNodeGroup(node, uid, compact, inspector);
    svg.appendChild(positioned);

    buildElements.push({ seg, nodeGroup: animated });
    prev = node;
  });

  canvas.appendChild(svg);

  if (willAnimate) {
    playConstruct(buildElements);
  } else {
    applyInstant(buildElements);
  }

  if (previousSvg) {
    window.requestAnimationFrame(() => {
      previousSvg.remove();
    });
  }
}

function buildStub(node, centerX) {
  const side = node.x >= centerX ? -1 : 1; // point away from the cascade
  const x1 = node.x + side * 16;
  const y1 = node.y - 10;
  const stub = document.createElementNS(SVG_NS, "path");
  stub.setAttribute("class", "lineage-stub");
  stub.setAttribute("aria-hidden", "true");
  stub.setAttribute("d", `M ${node.x} ${node.y} Q ${node.x + side * 8} ${node.y - 6} ${x1} ${y1}`);
  return stub;
}

function buildMarkDefs(uid) {
  const defs = document.createElementNS(SVG_NS, "defs");
  const symbol = document.createElementNS(SVG_NS, "symbol");
  symbol.id = `${uid}-mark`;
  symbol.setAttribute("viewBox", "-6 -6 12 12");

  const spine = document.createElementNS(SVG_NS, "line");
  spine.setAttribute("x1", "0");
  spine.setAttribute("y1", "-5");
  spine.setAttribute("x2", "0");
  spine.setAttribute("y2", "5");
  spine.setAttribute("stroke-width", "1.4");
  spine.setAttribute("stroke-linecap", "round");
  symbol.appendChild(spine);

  const rungA = document.createElementNS(SVG_NS, "line");
  rungA.setAttribute("x1", "-3.2");
  rungA.setAttribute("y1", "-2.2");
  rungA.setAttribute("x2", "3.2");
  rungA.setAttribute("y2", "-0.6");
  rungA.setAttribute("stroke-width", "1.1");
  rungA.setAttribute("stroke-linecap", "round");
  symbol.appendChild(rungA);

  const rungB = document.createElementNS(SVG_NS, "line");
  rungB.setAttribute("x1", "-3.2");
  rungB.setAttribute("y1", "2.2");
  rungB.setAttribute("x2", "3.2");
  rungB.setAttribute("y2", "0.6");
  rungB.setAttribute("stroke-width", "1.1");
  rungB.setAttribute("stroke-linecap", "round");
  symbol.appendChild(rungB);

  defs.appendChild(symbol);
  return defs;
}

/**
 * A node is two nested groups, and the nesting matters.
 *
 * The outer group carries the position as a transform *attribute*. The inner
 * group is the one that animates, and its scale comes from CSS. A CSS
 * transform replaces the attribute rather than combining with it, so putting
 * both on one element would drop every node onto the origin.
 */
function buildNodeGroup(node, uid, compact, inspector) {
  const positioned = document.createElementNS(SVG_NS, "g");
  positioned.setAttribute("class", "lineage-node-pos");
  positioned.setAttribute("transform", `translate(${node.x} ${node.y})`);

  const g = document.createElementNS(SVG_NS, "g");
  const labelled = node.terminal || node.major;
  g.setAttribute(
    "class",
    `lineage-node${node.terminal ? " is-terminal" : node.major ? "" : " is-minor"}`
  );
  g.setAttribute("tabindex", "0");
  g.setAttribute("role", "img");
  g.setAttribute(
    "aria-label",
    `${node.name}, ${node.rank}${node.terminal ? " — the organism itself" : ""}, TaxID ${node.taxid}`
  );
  positioned.appendChild(g);

  const detail = `${node.name} · ${node.rank} · TaxID ${node.taxid}`;
  g.addEventListener("mouseenter", () => inspector.show(detail));
  g.addEventListener("focus", () => inspector.show(detail));
  g.addEventListener("mouseleave", () => inspector.hide());
  g.addEventListener("blur", () => inspector.hide());

  if (node.terminal) {
    const ring = document.createElementNS(SVG_NS, "circle");
    ring.setAttribute("class", "lineage-tag-ring");
    ring.setAttribute("r", "9");
    g.appendChild(ring);
  }

  if (labelled) {
    const use = document.createElementNS(SVG_NS, "use");
    use.setAttribute("href", `#${uid}-mark`);
    use.setAttributeNS("http://www.w3.org/1999/xlink", "href", `#${uid}-mark`);
    use.setAttribute("class", `lineage-mark${node.terminal ? " is-terminal" : ""}`);
    if (node.terminal) {
      use.setAttribute("transform", "scale(1.3)");
    }
    g.appendChild(use);
  } else {
    const dot = document.createElementNS(SVG_NS, "circle");
    dot.setAttribute("class", "lineage-dot");
    dot.setAttribute("r", "2.6");
    g.appendChild(dot);
  }

  if (node.terminal) {
    const lines = appendLabel(g, node.name, "lineage-node-name is-terminal", 0, 26, "middle", compact);
    const extra = (lines - 1) * WRAP_LINE_OFFSET;

    const rank = document.createElementNS(SVG_NS, "text");
    rank.setAttribute("class", "lineage-node-rank");
    rank.setAttribute("text-anchor", "middle");
    rank.setAttribute("x", "0");
    rank.setAttribute("y", String(42 + extra));
    rank.textContent = node.rank;
    g.appendChild(rank);

    const rule = document.createElementNS(SVG_NS, "line");
    rule.setAttribute("class", "lineage-tag-ring");
    rule.setAttribute("x1", "-14");
    rule.setAttribute("x2", "14");
    rule.setAttribute("y1", String(50 + extra));
    rule.setAttribute("y2", String(50 + extra));
    rule.setAttribute("stroke-width", "2");
    g.appendChild(rule);
  } else if (node.major) {
    if (compact) {
      const lines = appendLabel(g, node.name, "lineage-node-name", 0, 18, "middle", compact);
      const extra = (lines - 1) * WRAP_LINE_OFFSET;

      const rank = document.createElementNS(SVG_NS, "text");
      rank.setAttribute("class", "lineage-node-rank");
      rank.setAttribute("text-anchor", "middle");
      rank.setAttribute("x", "0");
      rank.setAttribute("y", String(31 + extra));
      rank.textContent = node.rank;
      g.appendChild(rank);
    } else {
      const anchor = node.side >= 0 ? "start" : "end";
      const tx = node.side >= 0 ? 12 : -12;
      const lines = appendLabel(g, node.name, "lineage-node-name", tx, 4, anchor, compact);
      const extra = (lines - 1) * WRAP_LINE_OFFSET;

      const rank = document.createElementNS(SVG_NS, "text");
      rank.setAttribute("class", "lineage-node-rank");
      rank.setAttribute("text-anchor", anchor);
      rank.setAttribute("x", String(tx));
      rank.setAttribute("y", String(18 + extra));
      rank.textContent = node.rank;
      g.appendChild(rank);
    }
  } else {
    // A minor step only ever appears once the full lineage is open, and the
    // reader opened it to read the steps — so name them. Set smaller and
    // lighter than the ranks people are taught, which keeps the familiar
    // chain readable through a wall of unnamed clades.
    const anchor = node.side >= 0 ? "start" : "end";
    const tx = node.side >= 0 ? 10 : -10;

    const name = document.createElementNS(SVG_NS, "text");
    name.setAttribute("class", "lineage-node-name is-minor");
    name.setAttribute("text-anchor", anchor);
    name.setAttribute("x", String(tx));
    name.setAttribute("y", "1");
    name.textContent = node.name;
    g.appendChild(name);

    const rank = document.createElementNS(SVG_NS, "text");
    rank.setAttribute("class", "lineage-node-rank is-minor");
    rank.setAttribute("text-anchor", anchor);
    rank.setAttribute("x", String(tx));
    rank.setAttribute("y", "12");
    rank.textContent = node.rank;
    g.appendChild(rank);
  }

  return { positioned, animated: g };
}

// Roughly one 13px line's worth of extra vertical room — used to push the
// rank (and, on the terminal node, the rule beneath it) down when a name
// wraps, so a wrapped second line never sits under those instead of above.
const WRAP_LINE_OFFSET = 15;

/** Wraps long names onto a second line rather than letting them run past
 *  the canvas edge — a real reflow for narrow screens, not a smaller copy
 *  of the same layout. Returns how many lines it drew, so the caller can
 *  push whatever comes after it down to match. */
function appendLabel(g, text, className, x, y, anchor, compact) {
  const el = document.createElementNS(SVG_NS, "text");
  el.setAttribute("class", className);
  el.setAttribute("text-anchor", anchor);
  el.setAttribute("x", String(x));

  const maxChars = compact ? 15 : 26;
  if (text.length <= maxChars) {
    el.setAttribute("y", String(y));
    el.textContent = text;
    g.appendChild(el);
    return 1;
  }

  const breakAt = text.lastIndexOf(" ", maxChars);
  const first = breakAt > 0 ? text.slice(0, breakAt) : text.slice(0, maxChars);
  const second = breakAt > 0 ? text.slice(breakAt + 1) : text.slice(maxChars);

  const l1 = document.createElementNS(SVG_NS, "tspan");
  l1.setAttribute("x", String(x));
  l1.setAttribute("dy", String(y));
  l1.textContent = first;
  el.appendChild(l1);

  const l2 = document.createElementNS(SVG_NS, "tspan");
  l2.setAttribute("x", String(x));
  l2.setAttribute("dy", "1.15em");
  l2.textContent = second;
  el.appendChild(l2);

  g.appendChild(el);
  return 2;
}

/* ---------------------------------------------------------------
   Animation
   --------------------------------------------------------------- */

function playConstruct(elements) {
  elements.forEach((el, i) => {
    const base = i * TREE_STEP_MS;

    if (el.seg) {
      const len = el.seg.getTotalLength();
      el.seg.style.strokeDasharray = String(len);
      el.seg.style.strokeDashoffset = String(len);
      el.seg.style.transitionDelay = `${base}ms`;
    }

    el.nodeGroup.style.transitionDelay = `${base + TREE_STEP_MS * 0.55}ms`;
  });

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      elements.forEach((el) => {
        if (el.seg) el.seg.style.strokeDashoffset = "0";
        el.nodeGroup.classList.add("is-in");
      });
    });
  });
}

function applyInstant(elements) {
  elements.forEach((el) => {
    if (el.seg) el.seg.style.transitionDelay = "0ms";
    el.nodeGroup.style.transitionDelay = "0ms";
    el.nodeGroup.classList.add("is-in");
  });
}

/* ---------------------------------------------------------------
   Inspector — the restrained hover/focus detail readout
   --------------------------------------------------------------- */

function buildInspector(uid) {
  const el = document.createElement("p");
  el.className = "tree-inspector mono";
  el.id = `${uid}-inspector`;
  const placeholder = "Point at or tab through a branch point for its record.";
  el.textContent = placeholder;

  return {
    el,
    show(text) {
      el.textContent = text;
      el.classList.add("is-active");
    },
    hide() {
      el.textContent = placeholder;
      el.classList.remove("is-active");
    },
  };
}

/* ---------------------------------------------------------------
   Accessible text alternative
   --------------------------------------------------------------- */

function buildAccessibleList(taxon, uid) {
  const wrap = document.createElement("div");
  wrap.className = "visually-hidden";

  const heading = document.createElement("h4");
  heading.id = `${uid}-list-heading`;
  heading.textContent = "Full lineage, listed";
  wrap.appendChild(heading);

  const ol = document.createElement("ol");
  ol.setAttribute("aria-labelledby", heading.id);

  const raw = taxon.lineage || [];
  raw.forEach((n) => {
    const li = document.createElement("li");
    li.textContent = `${n.name} — ${n.rank}`;
    ol.appendChild(li);
  });

  const terminalLi = document.createElement("li");
  const displayName = taxon.common_name || taxon.scientific_name;
  terminalLi.textContent = `${taxon.scientific_name} (${displayName}) — ${taxon.rank}, the organism itself`;
  ol.appendChild(terminalLi);

  wrap.appendChild(ol);
  return wrap;
}

/* ---------------------------------------------------------------
   Utilities
   --------------------------------------------------------------- */

function clearNode(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}
