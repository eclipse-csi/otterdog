import {byId} from "./dom.js";

const COLLAPSED = "playground-examples-collapsed";

// The list of examples: the examples of the configuration guides of the documentation, and the current configuration
// of the organization of a project. The examples are filtered by their title and content, and opened as documents by
// open(button, {label, title, code}). The list collapses to a narrow bar leaving the space to the editors, onResize
// being called once their space changed.
export function setupExamples({buttons, examples, organization, open, onResize}) {
  const exampleOf = (button) => describeExample(button, examples, organization);
  for (const button of buttons) {
    button.addEventListener("click", () => open(button, exampleOf(button)));
  }
  const filter = byId("playground-examples-filter");
  filter.addEventListener("input", () => filterExamples(filter.value.trim().toLowerCase(), exampleOf));
  setupCollapse(onResize);
}

// the example of a button, its title starting with the title of its page
function describeExample(button, examples, organization) {
  const example = button.dataset.organization
    ? {title: "Current configuration", variant: null, code: organization.jsonnet}
    : examples[button.dataset.page].examples[button.dataset.example];
  const label = example.variant ? example.title + " (" + example.variant + ")" : example.title;
  const page = button.closest(".playground-examples-group").dataset.title;
  return {label, title: page + ": " + label, code: example.code};
}

function filterExamples(term, exampleOf) {
  let visible = 0;
  for (const group of document.querySelectorAll(".playground-examples-group")) {
    const matching = [...group.querySelectorAll(".playground-example")].filter((button) => {
      const {title, code} = exampleOf(button);
      button.hidden = ![title, code].some((text) => text.toLowerCase().includes(term));
      return !button.hidden;
    });
    group.hidden = matching.length === 0;
    visible += matching.length;
  }
  byId("playground-examples-empty").classList.toggle("d-none", visible > 0);
}

// the browser remembers whether the examples are collapsed, the page collapsing them before its first rendering
function setupCollapse(onResize) {
  const layout = document.querySelector(".playground-layout");
  const toggle = byId("playground-examples-toggle");
  const isCollapsed = () => layout.classList.contains(COLLAPSED);

  const collapse = (collapsed) => {
    layout.classList.toggle(COLLAPSED, collapsed);
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.title = collapsed ? "Show the examples" : "Hide the examples";
    toggle.querySelector("i").className = "fas " + (collapsed ? "fa-angles-right" : "fa-angles-left");
    onResize();
  };
  const switchCollapsed = () => {
    collapse(!isCollapsed());
    remember(COLLAPSED, isCollapsed());
  };

  collapse(isCollapsed());
  toggle.addEventListener("click", (event) => {
    event.stopPropagation();
    switchCollapsed();
  });
  // the whole bar of the collapsed examples expands them
  byId("playground-examples-header").addEventListener("click", () => isCollapsed() && switchCollapsed());
}

function remember(key, value) {
  try {
    localStorage.setItem(key, String(value));
  } catch {
    // no storage, e.g. in a private window
  }
}
