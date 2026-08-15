/**
 * Enhances the static search panel already in index.html: wires the form,
 * the example chips, and the small status line beside the field. Owns
 * nothing about results — it only ever reports a trimmed search term
 * upward through `onSubmit`.
 */

export function initSearch(panel, { onSubmit }) {
  const form = panel.querySelector("#searchForm");
  const input = panel.querySelector("#animalInput");
  const button = panel.querySelector("#searchButton");
  const buttonLabel = button.querySelector(".search-button-label");
  const status = panel.querySelector("#searchStatus");
  const chips = Array.from(panel.querySelectorAll(".example-chip"));

  let busy = false;

  function submit(term) {
    if (busy) return;

    const trimmed = term.trim();
    if (!trimmed) {
      status.textContent = "Enter an organism name to search.";
      status.classList.add("is-error");
      input.focus();
      return;
    }

    status.classList.remove("is-error");
    status.textContent = `Searching for “${trimmed}”…`;
    onSubmit(trimmed);
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submit(input.value);
  });

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const term = chip.dataset.animal || "";
      input.value = term;
      submit(term);
    });
  });

  return {
    setBusy(isBusy) {
      busy = isBusy;
      button.disabled = isBusy;
      button.setAttribute("aria-busy", String(isBusy));
      button.classList.toggle("is-loading", isBusy);
      buttonLabel.textContent = isBusy ? "Tracing…" : "Search";
      chips.forEach((chip) => {
        chip.disabled = isBusy;
      });
      if (!isBusy) {
        status.textContent = "";
        status.classList.remove("is-error");
      }
    },
    focusInput() {
      input.focus();
    },
    currentTerm() {
      return input.value;
    },
  };
}
