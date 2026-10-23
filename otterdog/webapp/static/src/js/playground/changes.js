import {changeCount, changeTree, changeTypeOf, diffConfigurations, formatValue} from "./diff.js";
import {actionLink, byId, element, icon} from "./dom.js";

const MAX_CHANGES = 500;
// more changes are collapsed, e.g. after loading an example in place of the configuration
const MAX_EXPANDED_CHANGES = 100;
const SYMBOLS = {added: "+", removed: "−", changed: "~"};

// The changes made to the configuration of the organization compared to its current configuration, grouped by section
// of the configuration and by element of its lists, a row for each changed property.
//
// Returns a function rendering the changes from the evaluations of the current configuration and of the configuration
// of the playground, also while another document is shown.
export function createChanges({name, showInOutput, showConfiguration}) {
  const pane = byId("playground-changes");
  const badge = byId("playground-changes-count");
  if (pane === null) {
    return () => {};
  }

  return (baseline, result, configurationShown) => {
    const changes = baseline?.value !== undefined && result?.value !== undefined
      ? diffConfigurations(baseline.value, result.value)
      : [];
    badge.textContent = changes.length;
    badge.classList.toggle("d-none", changes.length === 0);

    const message = messageOf(baseline, result, changes, name);
    const context = {name, showInOutput, value: result?.value};
    pane.replaceChildren(
      ...(configurationShown ? [] : [otherDocumentNote(name, showConfiguration)]),
      ...(message === null ? changesContent(changes, context) : [element("p", "small text-secondary mb-0", message)]),
    );
  };
}

// a message instead of the changes while they are not known, or if there are none
function messageOf(baseline, result, changes, name) {
  if (baseline === null) {
    return "Evaluating the current configuration of " + name + "…";
  }
  if (baseline.error !== undefined) {
    return "The current configuration of " + name + " could not be evaluated: " + baseline.error;
  }
  if (result === null) {
    return "Evaluating the configuration of " + name + "…";
  }
  if (result.error !== undefined) {
    return "The changes are shown once the configuration of " + name + " is evaluated without error.";
  }
  return changes.length === 0 ? "No change compared to the current configuration of " + name + "." : null;
}

function otherDocumentNote(name, showConfiguration) {
  const note = element("p", "small mb-2", "These changes are made to the configuration of " + name + ", not to the shown document. ");
  note.append(actionLink("Show the configuration", null, showConfiguration));
  return note;
}

function changesContent(changes, context) {
  const shown = changes.slice(0, MAX_CHANGES);
  const sectionContext = {...context, open: shown.length <= MAX_EXPANDED_CHANGES};
  const sections = changeTree(shown).map(([section, node]) => changeSection(section, node, sectionContext));
  const more = changes.length - shown.length;
  return [
    summaryOf(changes, context.name),
    ...sections,
    ...(more > 0 ? [element("p", "small text-secondary mt-2 mb-0", "… and " + more + " more changes.")] : []),
  ];
}

// the number of changes by type, and links expanding or collapsing all the groups of changes
function summaryOf(changes, name) {
  const summary = element("div", "d-flex flex-wrap align-items-center gap-2 mb-2");
  const total = changes.length === 1 ? "1 change" : changes.length + " changes";
  summary.append(element("span", "text-secondary", total + " compared to the current configuration of " + name));
  for (const type of Object.keys(SYMBOLS)) {
    const count = changes.filter((change) => change.type === type).length;
    if (count > 0) {
      summary.append(element("span", "badge playground-change-badge playground-change-" + type, SYMBOLS[type] + " " + count + " " + type));
    }
  }

  const toggles = element("span", "ms-auto text-nowrap");
  const openAll = (open) => () => {
    for (const group of summary.parentElement.querySelectorAll("details.playground-change-group")) {
      group.open = open;
    }
  };
  toggles.append(actionLink("Expand all", null, openAll(true)), " · ", actionLink("Collapse all", null, openAll(false)));
  summary.append(toggles);
  return summary;
}

function changeSection(section, node, context) {
  const title = section === "" ? "Organization" : section.charAt(0).toUpperCase() + section.slice(1).replaceAll("_", " ");
  const header = element("div", "playground-changes-section-header");
  header.append(element("span", null, title), " ", countBadge(node));
  // the sections that are part of the output link to it
  if (section !== "" && context.value[section] !== null && typeof context.value[section] === "object") {
    header.append(showLink("section:" + section, "the " + title.toLowerCase(), context));
  }

  const container = element("section", "playground-changes-section");
  container.append(header, ...nodeContent(node, {...context, section}));
  return container;
}

// the rows of the changed properties of a node, and the groups of its children
function nodeContent(node, context) {
  const rows = node.rows.length > 0 ? [changeRows(node.rows)] : [];
  return [...rows, ...[...node.children.values()].map((child) => changeGroup(child, context))];
}

function changeGroup(node, context) {
  // elements only containing another element are shown on one line, e.g. the ruleset of a repository
  const chain = [node];
  while (node.rows.length === 0 && node.change === null && node.children.size === 1) {
    node = [...node.children.values()][0];
    chain.push(node);
  }

  const group = element("details", "playground-change-group");
  // an element added or removed as a whole, e.g. a repository, is shown once expanded
  group.open = context.open && node.change === null;
  group.append(groupSummary(chain, context), groupContent(group, node, context));
  return group;
}

function groupSummary(chain, context) {
  const [first, last] = [chain[0], chain[chain.length - 1]];
  const summary = element("summary");
  summary.append(symbolOf(changeTypeOf(first)), " ");
  chain.forEach((node, index) => {
    summary.append(...(index > 0 ? [" ", element("span", "text-secondary", "›"), " "] : []));
    summary.append(...(node.kind === "" ? [] : [element("span", "text-secondary", node.kind), " "]));
    summary.append(element("span", "fw-semibold", node.label));
  });
  summary.append(" ", last.change === null
    ? countBadge(first)
    : element("span", "badge playground-change-badge playground-change-" + last.change.type, last.change.type));

  // the repositories that are part of the output link to it
  if (context.section === "repositories" && first.kind === "" && changeTypeOf(first) !== "removed") {
    summary.append(showLink("repository:" + first.label, "the repository " + first.label, context));
  }
  return summary;
}

function groupContent(group, node, context) {
  const content = element("div", "playground-change-content");
  if (node.change !== null) {
    group.addEventListener("toggle", () => {
      if (group.open && content.childElementCount === 0) {
        content.append(element("pre", "mb-1", JSON.stringify(node.change.value, null, 2)));
      }
    });
  }
  content.append(...nodeContent(node, context));
  return content;
}

// the changes of the properties of an element, one row each: symbol, property and values
function changeRows(rows) {
  const grid = element("div", "playground-change-rows");
  for (const {key, change} of rows) {
    const values = element("span", "playground-change-values");
    if (change.type === "changed") {
      values.append(valueOf(change.before, "removed"), element("span", "text-secondary", " → "), valueOf(change.after, "added"));
    } else {
      values.append(valueOf(change.value, change.type));
    }
    grid.append(symbolOf(change.type), element("span", "playground-change-key", key || "value"), values);
  }
  return grid;
}

function symbolOf(type) {
  const symbol = element("span", "playground-change-symbol playground-change-" + type, SYMBOLS[type]);
  symbol.title = type;
  return symbol;
}

function valueOf(value, type) {
  const result = element("span", "playground-change-value playground-change-value-" + type, formatValue(value));
  const text = JSON.stringify(value);
  if (text.length > 120) {
    result.title = text;
  }
  return result;
}

function countBadge(node) {
  return element("span", "badge rounded-pill text-bg-light border ms-1", changeCount(node));
}

function showLink(view, label, context) {
  const link = element("button", "btn btn-link btn-sm p-0 ms-1 playground-change-show");
  link.type = "button";
  link.title = "Show " + label + " in the output";
  link.setAttribute("aria-label", link.title);
  link.append(icon("fas fa-eye fa-xs"));
  link.addEventListener("click", (event) => {
    // not toggling the group the link is part of
    event.preventDefault();
    context.showInOutput(view);
  });
  return link;
}
