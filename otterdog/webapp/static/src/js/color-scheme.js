// The color mode of the dashboard, light or dark like the documentation: the one chosen with the toggle of the header,
// kept in the local storage, else the one of the system. includes/color-scheme.html sets it before the page renders,
// with the same storage key; this module changes it and gives the charts its colors.

export const STORAGE_KEY = "otterdog-color-scheme";

const LABELS = {light: "Switch to dark mode", dark: "Switch to light mode"};
const ICONS = {light: "fa-moon", dark: "fa-sun"};

export function currentScheme(root = document.documentElement) {
  return root.dataset.bsTheme === "dark" ? "dark" : "light";
}

export function nextScheme(scheme) {
  return scheme === "dark" ? "light" : "dark";
}

function storedScheme() {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function store(scheme) {
  try {
    localStorage.setItem(STORAGE_KEY, scheme);
  } catch {
    // the choice then lasts until the page is left
  }
}

// the toggle shows the mode it switches to, like the one of the documentation
function updateToggles(scheme) {
  for (const toggle of document.querySelectorAll("[data-otterdog-color-scheme-toggle]")) {
    toggle.setAttribute("aria-label", LABELS[scheme]);
    toggle.setAttribute("title", LABELS[scheme]);
    const icon = toggle.querySelector("i");
    icon?.classList.remove(...Object.values(ICONS));
    icon?.classList.add(ICONS[scheme]);
  }
}

// Chart.js draws on a canvas: the text, the grid and the gap between the slices of a doughnut take the colors of the
// mode, read from the variables of Bootstrap
function updateCharts() {
  const Chart = window.Chart;
  if (Chart === undefined) {
    return;
  }

  const style = getComputedStyle(document.body);
  Chart.defaults.color = style.getPropertyValue("--bs-secondary-color").trim();
  Chart.defaults.borderColor = style.getPropertyValue("--bs-border-color-translucent").trim();
  Chart.defaults.elements.arc.borderColor = style.getPropertyValue("--bs-body-bg").trim();
  for (const chart of Object.values(Chart.instances)) {
    chart.update();
  }
}

function apply(scheme) {
  document.documentElement.dataset.bsTheme = scheme;
  updateToggles(scheme);
  updateCharts();
}

export function initColorScheme() {
  apply(currentScheme());

  for (const toggle of document.querySelectorAll("[data-otterdog-color-scheme-toggle]")) {
    toggle.addEventListener("click", () => {
      const scheme = nextScheme(currentScheme());
      store(scheme);
      apply(scheme);
    });
  }

  // without a choice, the mode follows the one of the system when it changes
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (event) => {
    if (storedScheme() === null) {
      apply(event.matches ? "dark" : "light");
    }
  });
}
