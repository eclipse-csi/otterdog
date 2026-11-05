// The filters and the order of the projects pages (home/projects.html): the organizations are all in the page, grouped
// by their top-level project, each one with data attributes (includes/project-card.html) read here to hide the ones not
// matching, to sort them in their group and to count them. The filters are kept in the query string of the address of
// the page, so that a filtered list can be shared and survives a reload.

export const FIELDS = ["q", "group", "sort"];

// whether an organization, the dataset of its card, matches the filters, a filter without value matching every one
export function matches(organization, filters) {
  const query = (filters.q ?? "").trim().toLowerCase();
  if (query && !organization.name.includes(query)) {
    return false;
  }
  return !filters.group || organization.group === filters.group;
}

const number = (value) => Number(value ?? -1);

// the lowest values of a data attribute first, the unknown ones (-1) last, e.g. no statistics, score or change
function ascending(key) {
  const value = (organization) => (number(organization[key]) < 0 ? Infinity : number(organization[key]));
  return (a, b) => value(a) - value(b);
}

// the highest values of a data attribute first, the unknown ones (-1) last
function descending(key) {
  return (a, b) => number(b[key]) - number(a[key]);
}

// the orders of the organizations, by the data attributes of their cards (includes/project-card.html), the name
// breaking the ties
const ORDERS = {
  security: ascending("security"),
  "branch-protection": ascending("branchProtection"),
  "secret-scanning": ascending("secretScanning"),
  dependabot: ascending("dependabot"),
  "code-scanning": ascending("codeScanning"),
  scorecard: ascending("scorecard"),
  "pull-requests": descending("pullRequests"),
  blueprints: descending("blueprints"),
  "changed-recently": descending("changed"),
  "changed-long-ago": ascending("changed"),
  repositories: descending("repositories"),
};

export function compare(sort) {
  const order = ORDERS[sort];
  return (a, b) => (order ? order(a, b) : 0) || a.name.localeCompare(b.name);
}

export function countText(shown, total) {
  const noun = total === 1 ? "organization" : "organizations";
  return shown === total ? `${total} ${noun}` : `${shown} of ${total} ${noun}`;
}

// the button folding or unfolding all the groups: it folds them when one of them is open, else it unfolds them
export function groupsToggle(anyOpen) {
  return anyOpen
    ? {label: "Collapse all the groups", icon: "fa-angles-up"}
    : {label: "Expand all the groups", icon: "fa-angles-down"};
}

function readFilters(form) {
  return Object.fromEntries(FIELDS.map((field) => [field, form.elements[field]?.value ?? ""]));
}

export function initProjectFilters(form) {
  if (form === null) {
    return;
  }

  const groups = [...document.querySelectorAll("[data-otterdog-group]")];
  const total = document.querySelectorAll("[data-otterdog-project]").length;
  const count = form.querySelector("[data-otterdog-project-count]");
  const empty = document.querySelector("[data-otterdog-project-empty]");
  const toggle = form.querySelector("[data-otterdog-groups-toggle]");

  const anyOpen = () => groups.some((group) => !group.hidden && group.open);
  const updateToggle = () => {
    const {label, icon} = groupsToggle(anyOpen());
    toggle.setAttribute("aria-label", label);
    toggle.setAttribute("title", label);
    toggle.querySelector("i").className = `fas ${icon}`;
  };

  const params = new URLSearchParams(window.location.search);
  for (const field of FIELDS) {
    if (params.has(field) && form.elements[field]) {
      form.elements[field].value = params.get(field);
    }
  }

  const apply = () => {
    const filters = readFilters(form);
    let shown = 0;
    for (const group of groups) {
      const cards = group.querySelector("[data-otterdog-group-cards]");
      const organizations = [...cards.querySelectorAll("[data-otterdog-project]")];
      organizations.sort((a, b) => compare(filters.sort)(a.dataset, b.dataset));
      cards.append(...organizations);

      let visible = 0;
      for (const organization of organizations) {
        organization.hidden = !matches(organization.dataset, filters);
        visible += organization.hidden ? 0 : 1;
      }
      group.hidden = visible === 0;
      // a search or a top-level project shows its matches, even in the groups folded before
      if (visible > 0 && (filters.q.trim() || filters.group)) {
        group.open = true;
      }
      group.querySelector("[data-otterdog-group-count]").textContent =
        visible === organizations.length ? `${visible}` : `${visible} of ${organizations.length}`;
      shown += visible;
    }
    count.textContent = countText(shown, total);
    empty.hidden = shown > 0;
    updateToggle();

    const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
    const search = query.toString();
    window.history.replaceState(null, "", search ? `?${search}` : window.location.pathname);
  };

  toggle.addEventListener("click", () => {
    const open = !anyOpen();
    for (const group of groups) {
      group.open = open;
    }
    updateToggle();
  });
  for (const group of groups) {
    group.addEventListener("toggle", updateToggle);
  }

  form.addEventListener("input", apply);
  form.addEventListener("change", apply);
  form.addEventListener("submit", (event) => event.preventDefault());
  apply();
}
