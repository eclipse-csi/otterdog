// The filters and the order of the projects pages (home/projects.html): the organizations are all in the page, grouped
// by their top-level project, each one with data attributes (includes/project-card.html) read here to hide the ones not
// matching, to sort them in their group and to count them. The filters are kept in the query string of the address of
// the page, so that a filtered list can be shared and survives a reload.

export const FIELDS = ["q", "group", "state", "attention", "sort"];

function reasons(organization) {
  return organization.attention ? organization.attention.split(" ") : [];
}

// whether an organization, the dataset of its card, matches the filters, a filter without value matching every one
export function matches(organization, filters) {
  const query = (filters.q ?? "").trim().toLowerCase();
  if (query && !organization.name.includes(query)) {
    return false;
  }
  if (filters.group && organization.group !== filters.group) {
    return false;
  }
  if (filters.state && organization.state !== filters.state) {
    return false;
  }
  if (filters.attention === "any") {
    return reasons(organization).length > 0;
  }
  if (filters.attention && !reasons(organization).includes(filters.attention)) {
    return false;
  }
  return true;
}

const number = (value) => Number(value ?? -1);

// the orders of the organizations, the name breaking the ties
const ORDERS = {
  attention: (a, b) => reasons(b).length - reasons(a).length,
  // the least protected first, the organizations without statistics (-1) last
  security: (a, b) => {
    const value = (organization) => (number(organization.security) < 0 ? Infinity : number(organization.security));
    return value(a) - value(b);
  },
  repositories: (a, b) => number(b.repositories) - number(a.repositories),
  "pull-requests": (a, b) => number(b.pullRequests) - number(a.pullRequests),
};

export function compare(sort) {
  const order = ORDERS[sort];
  return (a, b) => (order ? order(a, b) : 0) || a.name.localeCompare(b.name);
}

export function countText(shown, total) {
  const noun = total === 1 ? "organization" : "organizations";
  return shown === total ? `${total} ${noun}` : `${shown} of ${total} ${noun}`;
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
  const summaries = [...document.querySelectorAll("[data-otterdog-project-summary]")];

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
      group.querySelector("[data-otterdog-group-count]").textContent =
        visible === organizations.length ? `${visible}` : `${visible} of ${organizations.length}`;
      shown += visible;
    }
    count.textContent = countText(shown, total);
    empty.hidden = shown > 0;

    for (const summary of summaries) {
      summary.setAttribute("aria-pressed", String(filters[summary.dataset.field] === summary.dataset.value));
    }

    const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
    const search = query.toString();
    window.history.replaceState(null, "", search ? `?${search}` : window.location.pathname);
  };

  // a figure of the summary filters the organizations it counts, a second click shows them all again
  for (const summary of summaries) {
    summary.addEventListener("click", () => {
      const pressed = summary.getAttribute("aria-pressed") === "true";
      form.elements.state.value = "";
      form.elements.attention.value = "";
      if (!pressed) {
        form.elements[summary.dataset.field].value = summary.dataset.value;
      }
      apply();
    });
  }

  form.addEventListener("input", apply);
  form.addEventListener("change", apply);
  form.addEventListener("submit", (event) => event.preventDefault());
  apply();
}
