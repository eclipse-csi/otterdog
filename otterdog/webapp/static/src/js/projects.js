// The filters of the projects pages (home/projects.html): the organizations are all in the page, each one with data
// attributes read by the filters, which hide the ones not matching. The filters are kept in the query string of the
// address of the page, so that a filtered list can be shared and survives a reload.

export const FIELDS = ["q", "group", "state", "settings"];

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
  if (filters.settings === "two-factor" && organization.twoFactor !== "false") {
    return false;
  }
  if (filters.settings === "write" && organization.permissions !== "write") {
    return false;
  }
  return true;
}

export function countText(shown, total) {
  const noun = total === 1 ? "organization" : "organizations";
  return shown === total ? `${total} ${noun}` : `${shown} of ${total} ${noun}`;
}

export function initProjectFilters(form) {
  if (form === null) {
    return;
  }

  const organizations = [...document.querySelectorAll("[data-otterdog-project]")];
  const count = form.querySelector("[data-otterdog-project-count]");
  const empty = document.querySelector("[data-otterdog-project-empty]");

  const params = new URLSearchParams(window.location.search);
  for (const field of FIELDS) {
    if (params.has(field) && form.elements[field]) {
      form.elements[field].value = params.get(field);
    }
  }

  const apply = () => {
    const filters = Object.fromEntries(FIELDS.map((field) => [field, form.elements[field]?.value ?? ""]));
    let shown = 0;
    for (const organization of organizations) {
      const visible = matches(organization.dataset, filters);
      organization.hidden = !visible;
      shown += visible ? 1 : 0;
    }
    count.textContent = countText(shown, organizations.length);
    empty.hidden = shown > 0;

    const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
    const search = query.toString();
    window.history.replaceState(null, "", search ? `?${search}` : window.location.pathname);
  };

  form.addEventListener("input", apply);
  form.addEventListener("change", apply);
  form.addEventListener("submit", (event) => event.preventDefault());
  apply();
}
