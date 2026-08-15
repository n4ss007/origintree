/**
 * The opening sequence: an anonymous branching structure grows on the dark
 * ground, particles settle into the air, the mark resolves, the wordmark
 * and tagline reveal, and the search panel arrives last.
 *
 * The branch geometry here has no relationship to any real taxon — it is
 * the same drawing grammar the lineage tree in tree.js uses (stroke-drawn
 * paths, small marker nodes, staggered timing), rehearsed once, in the
 * abstract, before a search has happened. That is deliberate: nothing in
 * this file should read as if it were asserting a real lineage.
 *
 * Any interaction during the sequence — scroll, click, keypress — jumps
 * straight to the finished composition. Under prefers-reduced-motion the
 * finished composition is simply what gets drawn, with no timers at all.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

const BRANCH_STAGGER_MS = 130;
const BRANCH_DURATION_MS = 620;

// An asymmetric two-level fork, not a symmetric decoration — the point is
// that it reads as a structure that branches, the way the lineage tree
// will once a search resolves.
const BRANCHES = [
  { from: [400, 526], to: [400, 424] }, // trunk
  { from: [400, 424], to: [226, 296], via: [328, 360] }, // left limb
  { from: [400, 424], to: [576, 300], via: [474, 360] }, // right limb
  { from: [226, 296], to: [112, 172], via: [164, 234] },
  { from: [226, 296], to: [302, 164], via: [278, 228] },
  { from: [576, 300], to: [498, 166], via: [524, 230] },
  { from: [576, 300], to: [688, 174], via: [634, 236] },
];

const NODE_POINTS = [
  [400, 424],
  [226, 296],
  [576, 300],
  [112, 172],
  [302, 164],
  [498, 166],
  [688, 174],
];

const STUBS = [
  { from: [112, 172], to: [84, 134], via: [96, 152] },
  { from: [112, 172], to: [140, 128], via: [128, 150] },
  { from: [302, 164], to: [322, 122], via: [312, 144] },
  { from: [688, 174], to: [716, 136], via: [704, 156] },
];

const PARTICLE_COUNT = 7;

export function initHero(root) {
  if (!root) return;

  // Everything in hero.css is visible by default so the page still makes
  // sense with no JS at all. This class is what switches the hero over to
  // "hidden, waiting to be revealed" — added synchronously, before
  // anything else, so there is nothing for a reader to see flash. The
  // transition those elements declare would otherwise animate this initial
  // hide too (visible article "closing" before the sequence even starts)
  // if script execution was delayed at all, so it borrows the same
  // no-transition guard the skip path uses, just for one frame.
  root.classList.add("js-anim", "no-anim");
  void root.offsetWidth;
  requestAnimationFrame(() => root.classList.remove("no-anim"));

  const svg = root.querySelector(".hero-phylogeny");
  const particlesEl = root.querySelector(".hero-particles");
  const emblem = root.querySelector(".hero-emblem");
  const wordLines = Array.from(root.querySelectorAll(".hero-word-line"));
  const tagline = root.querySelector(".hero-tagline");
  const panel = root.querySelector(".search-panel");
  const scrollCue = root.querySelector(".hero-scroll-cue");
  const skipButton = root.querySelector("#heroSkip");

  const { branchPaths, nodeCircles, stubPaths } = buildPhylogeny(svg);
  buildParticles(particlesEl, PARTICLE_COUNT);

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let timers = [];
  let settled = false;
  let skipController = null;

  function schedule(fn, ms) {
    timers.push(window.setTimeout(fn, ms));
  }

  function clearTimers() {
    timers.forEach((id) => window.clearTimeout(id));
    timers = [];
  }

  function reveal() {
    particlesEl.classList.add("is-in");
    emblem.classList.add("is-in");
    wordLines.forEach((line) => line.classList.add("is-in"));
    tagline.classList.add("is-in");
    panel.classList.add("is-in");
    scrollCue.classList.add("is-in");
  }

  function hideSkip() {
    skipButton.setAttribute("hidden", "");
    skipButton.setAttribute("aria-hidden", "true");
  }

  function finish() {
    if (settled) return;
    settled = true;
    clearTimers();
    if (skipController) skipController.abort();
    hideSkip();
    watchVisibility();
  }

  function playBranches() {
    branchPaths.forEach(({ path, length }, i) => {
      const delay = i * BRANCH_STAGGER_MS;
      path.style.strokeDasharray = String(length);
      path.style.strokeDashoffset = String(length);
      path.style.transitionDelay = `${delay}ms`;
    });

    nodeCircles.forEach((circle, i) => {
      const delay = i * BRANCH_STAGGER_MS + BRANCH_DURATION_MS * 0.7;
      circle.style.transitionDelay = `${delay}ms`;
    });

    stubPaths.forEach((path, i) => {
      path.style.transitionDelay = `${900 + i * 90}ms`;
    });

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        branchPaths.forEach(({ path }) => {
          path.style.strokeDashoffset = "0";
        });
        nodeCircles.forEach((circle) => circle.classList.add("is-in"));
        stubPaths.forEach((path) => path.classList.add("is-in"));
      });
    });
  }

  function playSequence() {
    playBranches();
    schedule(() => particlesEl.classList.add("is-in"), 1500);
    schedule(() => emblem.classList.add("is-in"), 2000);
    schedule(() => wordLines.forEach((line) => line.classList.add("is-in")), 2500);
    schedule(() => tagline.classList.add("is-in"), 2750);
    schedule(() => panel.classList.add("is-in"), 3150);
    schedule(() => scrollCue.classList.add("is-in"), 3700);
    schedule(finish, 4000);
  }

  function skipToFinished() {
    if (settled) return;
    settled = true;
    clearTimers();
    if (skipController) skipController.abort();

    root.classList.add("no-anim");
    branchPaths.forEach(({ path }) => {
      path.style.transitionDelay = "0ms";
      path.style.strokeDashoffset = "0";
    });
    nodeCircles.forEach((circle) => {
      circle.style.transitionDelay = "0ms";
      circle.classList.add("is-in");
    });
    stubPaths.forEach((path) => {
      path.style.transitionDelay = "0ms";
      path.classList.add("is-in");
    });
    reveal();
    hideSkip();

    // Force the snap to apply, then let future interactions (hover states
    // etc.) transition normally again.
    void root.offsetWidth;
    requestAnimationFrame(() => root.classList.remove("no-anim"));

    watchVisibility();
  }

  function watchVisibility() {
    if (!("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          particlesEl.classList.toggle("is-paused", !entry.isIntersecting);
        });
      },
      { threshold: 0 }
    );
    io.observe(root);
  }

  skipButton.addEventListener("click", skipToFinished);

  if (reducedMotion) {
    branchPaths.forEach(({ path }) => {
      path.style.strokeDashoffset = "0";
    });
    nodeCircles.forEach((circle) => circle.classList.add("is-in"));
    stubPaths.forEach((path) => path.classList.add("is-in"));
    reveal();
    hideSkip();
    settled = true;
    watchVisibility();
    return;
  }

  skipController = new AbortController();
  const opts = { passive: true, signal: skipController.signal };
  window.addEventListener("wheel", skipToFinished, opts);
  window.addEventListener("touchstart", skipToFinished, opts);
  window.addEventListener("keydown", skipToFinished, opts);
  window.addEventListener("pointerdown", skipToFinished, opts);

  playSequence();
}

/* ---------------------------------------------------------------
   Geometry
   --------------------------------------------------------------- */

function buildPhylogeny(svg) {
  const branchPaths = BRANCHES.map((segment) => {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("class", "hero-branch");
    path.setAttribute("d", segmentToD(segment));
    svg.appendChild(path);
    return { path, length: 0 };
  });

  // Length must be measured after the path is in the document.
  branchPaths.forEach((entry) => {
    entry.length = entry.path.getTotalLength();
  });

  const nodeCircles = NODE_POINTS.map(([x, y]) => {
    const circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("class", "hero-branch-node");
    circle.setAttribute("cx", String(x));
    circle.setAttribute("cy", String(y));
    circle.setAttribute("r", "3.6");
    svg.appendChild(circle);
    return circle;
  });

  const stubPaths = STUBS.map((segment) => {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("class", "hero-branch-stub");
    path.setAttribute("d", segmentToD(segment));
    svg.appendChild(path);
    return path;
  });

  return { branchPaths, nodeCircles, stubPaths };
}

function segmentToD(segment) {
  const [x0, y0] = segment.from;
  const [x1, y1] = segment.to;
  if (segment.via) {
    const [cx, cy] = segment.via;
    return `M ${x0} ${y0} Q ${cx} ${cy} ${x1} ${y1}`;
  }
  return `M ${x0} ${y0} L ${x1} ${y1}`;
}

/* ---------------------------------------------------------------
   Particles
   --------------------------------------------------------------- */

function buildParticles(container, count) {
  for (let i = 0; i < count; i += 1) {
    const span = document.createElement("span");
    span.className = "particle";
    span.style.setProperty("--px", `${8 + Math.random() * 84}%`);
    span.style.setProperty("--py", `${8 + Math.random() * 60}%`);
    span.style.setProperty("--size", `${1.5 + Math.random() * 2}px`);
    span.style.setProperty("--dur", `${13 + Math.random() * 10}s`);
    span.style.setProperty("--delay", `${-Math.random() * 14}s`);
    span.style.setProperty("--dx", `${(Math.random() - 0.5) * 40}px`);
    span.style.setProperty("--dy", `${-14 - Math.random() * 22}px`);
    span.style.setProperty("--peak", String(0.18 + Math.random() * 0.2));
    container.appendChild(span);
  }
}
