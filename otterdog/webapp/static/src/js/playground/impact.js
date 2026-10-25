import {changeTreeContent, changeValues, symbolOf} from "./changes.js";
import {diffConfigurations, patternOf} from "./diff.js";
import {actionLink, byId, element} from "./dom.js";
import {evaluationOf, filesOf} from "./evaluator.js";
import {isScalar} from "./values.js";

// the evaluators running at once, each one in its own worker
const MAX_EVALUATORS = 4;
// the groups of changes shown, the ones of most projects
const MAX_GROUPS = 50;

// the projects failing to evaluate with the edited default configuration first, then the ones that change
const LISTED = {failing: 0, changed: 1};

// The impact of the edited default configuration on the projects of the instance: their configurations, see the route
// /playground/configurations, are evaluated with the default configuration as published and as edited. The changes
// are grouped by property and values across the projects, e.g. 'repositories[*].has_wiki' from true to false, and the
// projects whose configuration changes are listed with their changes, like the ones failing to evaluate with the
// edited default configuration with their error. The configurations are evaluated by several evaluators at once, the
// evaluations with the published default configuration being kept for the next evaluations.
//
// The projects are only evaluated once the default configuration is edited, as they do not change otherwise.
//
// createEvaluator returns a new evaluator of files, see evaluator.js, normalize prepares a configuration to be
// evaluated with the files of the default configuration, published and edited() being these files as published and as
// edited, isEdited() telling whether they differ, and revision() the revision of the edited files. Returns the function
// telling that the default configuration has been edited.
export function createImpact({url, createEvaluator, normalize, published, isEdited, edited, revision}) {
  const button = byId("playground-impact-run");
  const hint = byId("playground-impact-hint");
  const progress = byId("playground-impact-progress");
  const results = byId("playground-impact");
  const count = byId("playground-impact-count");
  const baselines = new Map();
  let projects = null;
  let evaluators = null;
  // the revision of the default configuration that the projects have been evaluated with
  let evaluated = null;
  let running = false;

  async function run() {
    running = true;
    button.disabled = true;
    results.replaceChildren();
    const [template, version, started] = [edited(), revision(), performance.now()];
    try {
      projects ??= fetchProjects(url);
      const all = await projects;
      const available = all.filter((project) => project.jsonnet !== null);
      evaluators ??= Array.from({length: evaluatorCount()}, createEvaluator);
      let done = 0;
      showProgress(0, available.length);
      const impacts = await mapConcurrently(available, evaluators, async (evaluate, project) => {
        const code = normalize(project.jsonnet);
        if (!baselines.has(project.name)) {
          baselines.set(project.name, evaluationOf((snippet) => evaluate(filesOf(snippet, published)), code));
        }
        const before = await baselines.get(project.name);
        if (before.failed) {
          // evaluated again the next time, the evaluator failed rather than the configuration
          baselines.delete(project.name);
        }
        const after = await evaluationOf((snippet) => evaluate(filesOf(snippet, template)), code);
        showProgress(++done, available.length);
        return impactOf(project.name, before, after);
      });
      evaluated = version;
      render(impacts, all.length - available.length, performance.now() - started);
    } catch (e) {
      projects = null;
      results.replaceChildren(element("p", "small text-danger mb-0", "The projects could not be evaluated: " + e.message));
    } finally {
      running = false;
      progress.classList.add("d-none");
      update();
    }
  }

  function showProgress(done, total) {
    progress.classList.remove("d-none");
    Object.assign(progress.querySelector("progress"), {max: Math.max(total, 1), value: done});
    progress.querySelector("span").textContent = done + "/" + total;
  }

  function render(impacts, unavailable, duration) {
    const listed = impacts.filter((impact) => impact.kind in LISTED)
      .sort((a, b) => LISTED[a.kind] - LISTED[b.kind] || a.name.localeCompare(b.name));
    count.textContent = listed.length;
    count.classList.toggle("d-none", listed.length === 0);

    const projects = listed.map((impact) => [impact.name, projectImpact(impact, listed.length === 1)]);
    const filterNote = element("p", "small mb-1 d-none");
    // shows the projects having a group of changes, all of them without
    const filter = (group) => {
      const names = new Set(group?.projects ?? projects.map(([name]) => name));
      projects.forEach(([name, details]) => (details.hidden = !names.has(name)));
      filterNote.classList.toggle("d-none", group === null);
      if (group !== null) {
        filterNote.replaceChildren("Projects with the change of ", element("code", null, group.pattern), " · ",
          actionLink("Show all the projects", null, () => filter(null)));
      }
    };
    const groups = aggregateChanges(listed);
    results.replaceChildren(
      summaryOf(impacts, unavailable, duration),
      element("p", "small text-warning-emphasis mb-2 d-none playground-impact-outdated",
        "The default configuration has been edited since, evaluate the projects again to see the impact of these changes."),
      ...(groups.length > 0 ? [groupedChanges(groups, filter)] : []),
      ...(listed.length > 0 ? [element("div", "playground-changes-section-header", "Projects"), filterNote] : []),
      ...projects.map(([, details]) => details),
    );
  }

  // The projects can be evaluated once the default configuration is edited, the evaluation shown being outdated once
  // it is edited again. Once its changes are discarded, the projects do not change anymore.
  function update() {
    const edited = isEdited();
    button.disabled = running || !edited;
    showHint(hint, button, !edited);
    if (!edited && !running) {
      evaluated = null;
      results.replaceChildren();
      count.classList.add("d-none");
    }
    results.querySelector(".playground-impact-outdated")?.classList.toggle("d-none", evaluated === revision());
  }

  button.addEventListener("click", run);
  update();
  return update;
}

// the hint telling why the button is disabled, shown when it is hovered, and describing it for assistive technologies
function showHint(hint, button, shown) {
  const tooltip = window.bootstrap.Tooltip.getOrCreateInstance(hint);
  if (shown) {
    tooltip.enable();
    button.setAttribute("aria-describedby", "playground-impact-why");
  } else {
    tooltip.hide();
    tooltip.disable();
    button.removeAttribute("aria-describedby");
  }
}

async function fetchProjects(url) {
  const response = await fetch(url, {headers: {Accept: "application/json"}});
  if (!response.ok) {
    throw new Error(response.status + " " + response.statusText);
  }
  return (await response.json()).projects;
}

const evaluatorCount = () => Math.max(1, Math.min(MAX_EVALUATORS, (navigator.hardwareConcurrency ?? 2) - 1));

// Runs a task for each item, each runner, e.g. an evaluator, running one task at a time, and returns their results in
// the order of the items.
export async function mapConcurrently(items, runners, task) {
  const results = [];
  let next = 0;
  // each runner takes the next item once it is done with its item
  const run = async (runner) => {
    if (next < items.length) {
      const index = next++;
      results[index] = await task(runner, items[index]);
      await run(runner);
    }
  };
  await Promise.all(runners.map(run));
  return results;
}

// The impact of the edited default configuration on a project: its changes, or the error of its evaluation, the
// projects whose configuration fails with the published default configuration too being apart, like the ones that
// could not be evaluated because the evaluator failed, e.g. without memory left.
export function impactOf(name, before, after) {
  if (before.failed || after.failed) {
    return {name, kind: "unevaluated", error: before.failed ? before.error : after.error};
  }
  if (before.error !== undefined) {
    return {name, kind: "broken", error: before.error};
  }
  if (after.error !== undefined) {
    return {name, kind: "failing", error: after.error};
  }
  const changes = diffConfigurations(before.value, after.value);
  return {name, kind: changes.length === 0 ? "unchanged" : "changed", changes};
}

// Groups the changes of the projects by property and values, e.g. 'repositories[*].has_wiki' changed from true to
// false: {change, pattern, count, projects}, change being one of these changes, count their number, and projects the
// names of the projects having them, the groups of most projects first.
export function aggregateChanges(impacts) {
  const groups = new Map();
  for (const {name, changes = []} of impacts) {
    for (const change of changes) {
      const pattern = patternOf(change.segments);
      const key = JSON.stringify([change.type, pattern, ...valuesOf(change)]);
      if (!groups.has(key)) {
        groups.set(key, {change, pattern, count: 0, projects: new Set()});
      }
      groups.get(key).count++;
      groups.get(key).projects.add(name);
    }
  }
  return [...groups.values()]
    .map((group) => ({...group, projects: [...group.projects]}))
    .sort((a, b) => b.projects.length - a.projects.length || b.count - a.count || a.pattern.localeCompare(b.pattern));
}

// the values of a change that its group has, the objects added or removed being grouped whatever their values
const valuesOf = (change) => (change.type === "changed" ? [change.before, change.after] : [isScalar(change.value) ? change.value : null]);

// the groups of changes, the number of their projects showing these projects when clicked
function groupedChanges(groups, filter) {
  const grid = element("div", "playground-impact-changes");
  for (const group of groups.slice(0, MAX_GROUPS)) {
    const projects = group.projects.length;
    const link = actionLink(group.count + " in " + projects + " " + plural(projects, "project", "projects"), "text-nowrap", () => filter(group));
    link.title = "Show the projects with this change";
    grid.append(symbolOf(group.change.type), element("span", "playground-change-key", group.pattern), groupValues(group.change), link);
  }
  const section = element("section", "mb-2");
  section.append(element("div", "playground-changes-section-header", "Changes"), grid);
  if (groups.length > MAX_GROUPS) {
    section.append(element("p", "small text-secondary mb-0", "… and " + (groups.length - MAX_GROUPS) + " more changes."));
  }
  return section;
}

// the values of a group of changes, only the type of the changes of objects, whose values differ between projects
function groupValues(change) {
  return change.type !== "changed" && !isScalar(change.value) ? element("span", "text-secondary", change.type) : changeValues(change);
}

function summaryOf(impacts, unavailable, duration) {
  const ofKind = (kind) => impacts.filter((impact) => impact.kind === kind);
  const [changed, failing, unchanged] = ["changed", "failing", "unchanged"].map((kind) => ofKind(kind).length);
  const summary = element("p", "small mb-2");
  summary.append(
    element("span", "fw-semibold", changed + " of " + impacts.length + " projects " + plural(changed, "changes", "change")),
    " with the edited default configuration",
    ...(failing > 0 ? [", ", element("span", "text-danger fw-semibold", failing + " " + plural(failing, "fails", "fail") + " to evaluate")] : []),
    ", " + unchanged + " " + plural(unchanged, "is", "are") + " unchanged (" + (duration / 1000).toFixed(1) + " s).",
  );
  const notes = [];
  if (ofKind("broken").length > 0) {
    notes.push("Failing with the published default configuration too: " + namesOf(ofKind("broken")) + ".");
  }
  if (ofKind("unevaluated").length > 0) {
    const [first] = ofKind("unevaluated");
    notes.push("Not evaluated, the evaluator failed (" + first.error + "): " + namesOf(ofKind("unevaluated")) + ". Evaluate the projects again.");
  }
  if (unavailable > 0) {
    notes.push(unavailable === 1
      ? "1 project is not evaluated, its configuration has not been fetched with its source yet."
      : unavailable + " projects are not evaluated, their configuration has not been fetched with its source yet.");
  }
  summary.append(...notes.map((note) => element("span", "d-block text-secondary", note)));
  return summary;
}

const plural = (count, singular, several) => (count === 1 ? singular : several);

const namesOf = (impacts) => impacts.map((impact) => impact.name).join(", ");

// a project with its changes or its error, shown once expanded
function projectImpact(impact, open) {
  const group = element("details", "playground-change-group");
  const summary = element("summary");
  const failing = impact.kind === "failing";
  const badge = element("span", "badge ms-1 " + (failing ? "text-bg-danger" : "rounded-pill text-bg-light border"),
    failing ? "error" : String(impact.changes.length));
  const link = element("a", "ms-2 small", "playground");
  link.href = "/projects/" + encodeURIComponent(impact.name) + "/playground";
  link.target = "_blank";
  link.rel = "noopener";
  summary.append(element("span", "fw-semibold", impact.name), " ", badge, " ", link);

  const content = element("div", "playground-change-content");
  group.addEventListener("toggle", () => {
    if (group.open && content.childElementCount === 0) {
      content.append(...(failing ? [element("pre", "small text-danger mb-1", impact.error)] : changeTreeContent(impact.changes)));
    }
  });
  group.append(summary, content);
  group.open = open;
  return group;
}
