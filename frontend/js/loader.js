/**
 * The loading indicator: four organisms, lit one at a time.
 *
 * A spinner says "something is happening". This says what is happening —
 * OriginTree is working its way through the record, organism by organism,
 * while NCBI answers. The four are drawn in the same flat green as the
 * lineage marks so they read as part of the same family of objects.
 *
 * The silhouettes are built from plain circles and short paths rather than
 * detailed artwork, because they are shown at around twenty pixels and
 * anything finer turns to mud.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

/** Milliseconds each organism stays lit. Slow enough to read as a sequence. */
const STEP_MS = 420;

/**
 * Each entry draws into a 24×24 box.
 *
 * Kept as data rather than markup so the set can be extended — a fifth
 * organism only needs another entry here.
 */
const ORGANISMS = [
  {
    name: "bear",
    shapes: [
      { el: "circle", cx: 7.2, cy: 7.4, r: 3.1 },
      { el: "circle", cx: 16.8, cy: 7.4, r: 3.1 },
      { el: "circle", cx: 12, cy: 13.4, r: 6.4 },
    ],
  },
  {
    name: "lion",
    shapes: [
      // the mane reads as a ring behind the face at this size
      { el: "circle", cx: 12, cy: 12, r: 8.2, opacity: 0.45 },
      { el: "circle", cx: 12, cy: 12, r: 5.2 },
      { el: "circle", cx: 7.6, cy: 7.6, r: 1.9 },
      { el: "circle", cx: 16.4, cy: 7.6, r: 1.9 },
    ],
  },
  {
    name: "bird",
    shapes: [
      // body sweeping back to a tail, head and beak in profile
      { el: "path", d: "M14.4 10.2 C17.6 11 19.6 13.4 19.6 16 C19.6 18.6 17.2 20.4 14 20.4 C10.4 20.4 7.4 18 6.6 14.8 Z" },
      { el: "circle", cx: 13.6, cy: 8.2, r: 3.2 },
      { el: "path", d: "M16.6 7.2 L20.8 8.4 L16.6 10 Z" },
    ],
  },
  {
    name: "elephant",
    shapes: [
      { el: "circle", cx: 14, cy: 10.6, r: 5.8 },
      { el: "circle", cx: 7.4, cy: 10.4, r: 4.4, opacity: 0.45 },
      // trunk
      { el: "path", d: "M15.2 15.6 C15.6 18.4 15 20.4 13.2 21.2 C12.4 21.6 11.6 21.2 11.6 20.4 C11.6 19.8 12 19.6 12.6 19.4 C13.4 19 13.6 17.6 13.2 15.8 Z" },
    ],
  },
];

/**
 * Builds the indicator and starts it.
 *
 * @param   {string} [label] text shown beside the organisms
 * @returns {{el: HTMLElement, stop: () => void}}
 *          `el` to place; `stop()` to halt the timer. Callers must call
 *          stop() when their request settles — a timer left running keeps
 *          firing against a node nobody is looking at.
 */
export function createLoader(label = "Tracing lineage…") {
  const wrap = document.createElement("div");
  wrap.className = "organism-loader";
  wrap.setAttribute("role", "status");

  const track = document.createElement("div");
  track.className = "organism-loader-track";
  track.setAttribute("aria-hidden", "true");

  const icons = ORGANISMS.map((organism, index) => {
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("class", `organism-icon${index === 0 ? " is-active" : ""}`);
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", "22");
    svg.setAttribute("height", "22");
    svg.setAttribute("focusable", "false");

    organism.shapes.forEach((shape) => {
      const node = document.createElementNS(SVG_NS, shape.el);

      Object.entries(shape).forEach(([key, value]) => {
        if (key !== "el") node.setAttribute(key, String(value));
      });

      svg.appendChild(node);
    });

    track.appendChild(svg);
    return svg;
  });

  wrap.appendChild(track);

  const text = document.createElement("span");
  text.className = "organism-loader-label";
  text.textContent = label;
  wrap.appendChild(text);

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let timer = null;

  if (!reduced) {
    let current = 0;

    timer = window.setInterval(() => {
      icons[current].classList.remove("is-active");
      current = (current + 1) % icons.length;
      icons[current].classList.add("is-active");
    }, STEP_MS);
  } else {
    // Static under reduced motion: all four visible, the first marked, no
    // timer at all rather than a slower one.
    wrap.classList.add("is-static");
  }

  function stop() {
    if (timer !== null) {
      window.clearInterval(timer);
      timer = null;
    }
  }

  return { el: wrap, stop };
}
