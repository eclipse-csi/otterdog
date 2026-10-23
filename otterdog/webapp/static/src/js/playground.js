// The playground evaluates a configuration with the default configuration of an organization in the browser, the
// content of the playground is never sent to the server. The page (templates/home/playground.html) renders its
// markup and passes its data to createPlayground, CodeMirror 5 and Bootstrap are loaded as vendor scripts.
//
// The modules of playground/ implement the parts of the playground, this module connects them with the controls of
// the page.

import {createChanges} from "./playground/changes.js";
import {defaultsSnippet, explicitValues} from "./playground/defaults.js";
import {createDocuments} from "./playground/documents.js";
import {actionLink, byId, flash, markCurrent} from "./playground/dom.js";
import {createEvaluator, createScheduler} from "./playground/evaluator.js";
import {createFiles} from "./playground/files.js";
import {createOutput} from "./playground/output.js";
import {
  MAIN_FILE,
  MAX_ENCODED_SNIPPET,
  encodeSnippet,
  errorLocations,
  normalizeSnippet,
  snippetOfHash,
} from "./playground/snippets.js";

// delay after the last change before evaluating the playground again
const EVALUATION_DELAY = 300;

const EXAMPLES_COLLAPSED = "playground-examples-collapsed";

const EDITOR_OPTIONS = {
  mode: "jsonnet",
  lineNumbers: true,
  indentUnit: 2,
  tabSize: 2,
  matchBrackets: true,
  scrollbarStyle: "native",
};

const INDENTATION_KEYS = {
  Tab: (cm) => (cm.somethingSelected() ? cm.indentSelection("add") : cm.execCommand("insertSoftTab")),
  "Shift-Tab": (cm) => cm.indentSelection("subtract"),
};

// the output of a document shown for the first time
const INITIAL_OUTPUT = {view: "", scroll: {left: 0, top: 0}};

export function createPlayground(data) {
  const playground = connect(data);
  setupExamples(playground);
  setupReset(playground);
  setupCopyLink(playground);
  setupTemplateChoice(playground);
  setupProposal(playground);
  setupCollapsedExamples(playground);
  openDocuments(playground);
}

// creates the parts of the playground, connected through the returned object
function connect(data) {
  const textarea = byId("playground-jsonnet");
  const p = {
    data,
    organization: data.organization,
    defaultContent: textarea.value.replace(/\s+$/, ""),
    normalize: (code) => normalizeSnippet(code, data.templateFiles.map((file) => file.filename), data.defaultConfig),
    exampleButtons: document.querySelectorAll(".playground-example"),
    organizationDocument: null,
    // the evaluation of the current configuration of the organization, see createScheduler
    baseline: null,
    // the view and position of the output to restore once the active document is evaluated
    restoredOutput: null,
  };

  p.editor = window.CodeMirror.fromTextArea(textarea, {...EDITOR_OPTIONS, extraKeys: INDENTATION_KEYS});
  p.files = createFiles({
    editor: p.editor,
    templateFiles: data.templateFiles,
    defaultConfig: data.defaultConfig,
    editorOptions: EDITOR_OPTIONS,
    onShow: () => p.documents.render(),
  });
  p.output = createOutput(p.files);
  p.confirm = createConfirmation();
  p.documents = createDocuments({
    editor: p.editor,
    isEditorShown: () => p.files.shown() === MAIN_FILE,
    onActivate: (d, previous) => activated(p, d, previous),
    confirmClose: (d, close) => p.confirm("Closing the example \"" + d.label + "\" discards your changes to it.", "Close", close),
  });
  p.changes = createChanges({
    name: p.organization?.name,
    showInOutput: (view) => showInOutput(p, view),
    showConfiguration: () => p.documents.activate(p.organizationDocument),
  });
  p.evaluate = evaluation(p);
  p.schedule = createScheduler(p.evaluate, {
    current: () => p.documents.active(),
    evaluating: () => p.output.setStatus("evaluating", "Evaluating…"),
    evaluated: (d) => d === p.organizationDocument && organizationEvaluated(p),
    show: (d) => showEvaluation(p, d),
  });

  p.editor.on("change", (cm, change) => {
    if (p.documents.update()) {
      updateButtons(p);
    }
    p.schedule(change.origin === "setValue" ? 0 : EVALUATION_DELAY);
  });
  return p;
}

// Returns a function evaluating a snippet with the files of the default configuration. The current configuration of
// the organization is evaluated once, to show the changes made to it.
function evaluation(p) {
  const evaluateFiles = createEvaluator();
  const evaluate = (code) => evaluateFiles(filesOf(code, p.data.templateFiles));
  if (p.organization === null) {
    return evaluate;
  }

  const baselineCode = p.normalize(p.organization.jsonnet);
  const baselineJson = evaluate(baselineCode);
  baselineJson
    .then((json) => (p.baseline = {value: JSON.parse(json)}), (e) => (p.baseline = {error: e.message}))
    .finally(() => renderChanges(p));
  return (code) => (code === baselineCode ? baselineJson : evaluate(code));
}

function filesOf(code, templateFiles) {
  return Object.fromEntries([[MAIN_FILE, code], ...templateFiles.map((file) => [file.filename, file.content])]);
}

function activated(p, d, previous) {
  if (d !== previous) {
    if (previous !== null) {
      previous.output = p.output.state() ?? previous.output;
    }
    p.restoredOutput = d.output ?? INITIAL_OUTPUT;
    p.schedule(0);
  }
  p.files.show(MAIN_FILE);
  markCurrent(p.exampleButtons, d.button);
  updateButtons(p);
  renderChanges(p);
}

// shows the evaluation of the active document, at its previous view and position if it has just been activated
function showEvaluation(p, d) {
  const restored = p.restoredOutput;
  p.restoredOutput = null;
  if (d.result.error === undefined) {
    p.files.clearErrors();
    p.output.showValue(d.result.value, d.result.duration, restored);
    highlightDefaultValues(p, d);
    return;
  }

  clearDefaultValues(d);
  const locations = errorLocations(d.result.error);
  p.files.markErrors(locations, d.result.error.split("\n")[0]);
  p.output.showError(d.result.error, locations);
}

// ---- explicit values identical to the values of the default configuration of otterdog (its base_template, e.g.
// otterdog-defaults), not to the defaults of GitHub: these lines can be removed, the values are inherited

async function highlightDefaultValues(p, d) {
  const code = d.doc.getValue();
  if (d.defaultValues?.code !== code) {
    const ranges = await defaultValueRanges(p, code);
    if (d.doc.getValue() !== code) {
      // changed meanwhile, highlighted once evaluated again
      return;
    }
    clearDefaultValues(d);
    const title = "Same value as in the default configuration " + p.data.defaultConfiguration
      + ": this line can be removed, the value is inherited.";
    const mark = ({from, to}) => d.doc.markText(d.doc.posFromIndex(from), d.doc.posFromIndex(to), {className: "playground-default-value", title});
    d.defaultValues = {code, next: 0, marks: ranges.map(mark)};
  }
  if (d === p.documents.active()) {
    p.output.setNote(defaultValuesNote(p, d));
  }
}

// the ranges of the explicit values that are identical to the default configuration
async function defaultValueRanges(p, code) {
  const values = explicitValues(code);
  const snippet = defaultsSnippet(code, values);
  if (snippet === null) {
    return [];
  }
  try {
    const identical = JSON.parse(await p.evaluate(snippet));
    return values.filter((value, index) => identical[index] === true);
  } catch (e) {
    // e.g. a call of the default configuration that is not supported by the template, nothing is highlighted
    return [];
  }
}

function clearDefaultValues(d) {
  d.defaultValues?.marks.forEach((mark) => mark.clear());
  d.defaultValues = null;
}

// the number of values identical to the default configuration, going to the next one
function defaultValuesNote(p, d) {
  const {marks} = d.defaultValues;
  if (marks.length === 0) {
    return null;
  }
  const text = marks.length === 1 ? "1 value already set by the default configuration" : marks.length + " values already set by the default configuration";
  const note = actionLink(text, "link-secondary", () => {
    const location = marks[d.defaultValues.next++ % marks.length].find();
    if (location !== undefined) {
      p.files.goTo(MAIN_FILE, location);
    }
  });
  note.title = "Values that the default configuration " + p.data.defaultConfiguration + " already sets, the defaults of GitHub"
    + " are not taken into account: they are inherited, and these lines can be removed. Click to go to the next one.";
  return note;
}

function organizationEvaluated(p) {
  renderChanges(p);
  updateButtons(p);
}

// the changes are the ones of the configuration of the organization, also while another document is shown
function renderChanges(p) {
  if (p.organizationDocument !== null) {
    p.changes(p.baseline, p.organizationDocument.result, p.documents.active() === p.organizationDocument);
  }
}

// shows a section or a repository in the output of the configuration of the organization
function showInOutput(p, view) {
  window.bootstrap.Tab.getOrCreateInstance(byId("playground-output-tab")).show();
  if (p.documents.active() === p.organizationDocument) {
    p.output.show(view);
  } else {
    p.documents.activate(p.organizationDocument);
    p.restoredOutput = {...INITIAL_OUTPUT, view};
  }
}

// the reset of the active document, and the proposal of the changes to the configuration of the organization
function updateButtons(p) {
  const d = p.documents.active();
  const reset = byId("playground-reset");
  reset.disabled = !d.modified;
  reset.title = "Restore " + restoredContentOf(p, d);

  const propose = byId("playground-propose");
  if (propose !== null) {
    // nothing to propose without changes, nor a configuration failing to evaluate
    propose.disabled = !p.organizationDocument.modified || p.organizationDocument.result?.error !== undefined;
  }
}

function restoredContentOf(p, d) {
  return {
    organization: "the current configuration of " + p.organization?.name,
    snippet: "the content as it was loaded",
    example: "the example",
  }[d.kind];
}

// Returns a function asking to confirm an action discarding changes, cancel being called if it is not confirmed.
function createConfirmation() {
  const modalElement = byId("playground-overwrite-modal");
  const modal = window.bootstrap.Modal.getOrCreateInstance(modalElement);
  const confirmButton = byId("playground-overwrite-confirm");
  let pending = null;

  confirmButton.addEventListener("click", () => {
    const action = pending?.action;
    pending = null;
    modal.hide();
    action?.();
  });
  modalElement.addEventListener("hidden.bs.modal", () => {
    const cancel = pending?.cancel;
    pending = null;
    cancel?.();
  });

  return (message, label, action, cancel = null) => {
    pending = {action, cancel};
    byId("playground-overwrite-message").textContent = message;
    confirmButton.textContent = label;
    modal.show();
  };
}

// ---- examples: opened as documents, filtered by their title and content

function setupExamples(p) {
  for (const button of p.exampleButtons) {
    button.addEventListener("click", () => p.documents.open(button, () => exampleDocument(p, button)));
  }
  const filter = byId("playground-examples-filter");
  filter.addEventListener("input", () => filterExamples(p, filter.value.trim().toLowerCase()));
}

function exampleDocument(p, button) {
  const example = exampleOf(p, button);
  const page = button.closest(".playground-examples-group").dataset.title;
  return p.documents.create("example", labelOf(example), page + ": " + labelOf(example), p.normalize(example.code), button);
}

function exampleOf(p, button) {
  if (button.dataset.organization) {
    return {title: "Current configuration", variant: null, code: p.organization.jsonnet};
  }
  return p.data.examples[button.dataset.page].examples[button.dataset.example];
}

const labelOf = (example) => (example.variant ? example.title + " (" + example.variant + ")" : example.title);

function filterExamples(p, term) {
  let visible = 0;
  for (const group of document.querySelectorAll(".playground-examples-group")) {
    const matching = [...group.querySelectorAll(".playground-example")].filter((button) => {
      const example = exampleOf(p, button);
      button.hidden = ![group.dataset.title, labelOf(example), example.code].some((text) => text.toLowerCase().includes(term));
      return !button.hidden;
    });
    group.hidden = matching.length === 0;
    visible += matching.length;
  }
  byId("playground-examples-empty").classList.toggle("d-none", visible > 0);
}

// ---- controls of the toolbar

function setupReset(p) {
  byId("playground-reset").addEventListener("click", () => {
    const d = p.documents.active();
    p.confirm("Resetting restores " + restoredContentOf(p, d) + ", your changes will be lost.", "Reset", () => {
      d.doc.setValue(d.original);
      if (d === p.documents.active()) {
        p.editor.scrollTo(0, 0);
      }
    });
  });
}

function setupCopyLink(p) {
  const button = byId("playground-copy-link");
  button.addEventListener("click", async () => {
    const encoded = encodeSnippet(p.editor.getValue());
    if (encoded.length > MAX_ENCODED_SNIPPET) {
      flash(button, "fa-triangle-exclamation", "Too long for a link");
      return;
    }

    const url = window.location.origin + window.location.pathname + window.location.search + "#code=" + encoded;
    try {
      await navigator.clipboard.writeText(url);
      flash(button, "fa-check", "Link copied");
    } catch (e) {
      // e.g. no clipboard outside of secure contexts
      window.prompt("Copy the link to the playground:", url);
    }
  });
}

// the global playground reloads with the chosen default configuration, keeping the shown document
function setupTemplateChoice(p) {
  const select = byId("playground-template");
  if (select !== null) {
    const selected = select.value;
    select.addEventListener("change", () => changeTemplate(p, select.value, () => (select.value = selected)));
  }
}

function changeTemplate(p, template, cancel) {
  const url = templateUrl(template);
  const code = p.editor.getValue();
  const encoded = code === p.defaultContent ? "" : encodeSnippet(code);
  if (encoded.length > MAX_ENCODED_SNIPPET) {
    const message = "The shown document is too long to be kept when changing the default configuration, your changes will be lost.";
    p.confirm(message, "Change", () => window.location.assign(url), cancel);
    return;
  }

  const target = encoded === "" ? url : url + "#code=" + encoded;
  if (p.documents.othersModified()) {
    const message = "Changing the default configuration only keeps the shown document, your changes to the other ones will be lost.";
    p.confirm(message, "Change", () => window.location.assign(target), cancel);
    return;
  }
  window.location.assign(target);
}

function templateUrl(template) {
  const url = new URL(window.location.href);
  url.hash = "";
  if (template === "") {
    url.searchParams.delete("template");
  } else {
    url.searchParams.set("template", template);
  }
  return url.href;
}

// The changes to the configuration of the organization are proposed as a pull request from the account of the user:
// browsers do not let the playground fill the editor of GitHub, the user pastes the copied configuration into it.
function setupProposal(p) {
  const button = byId("playground-propose");
  if (button === null) {
    return;
  }

  const modal = window.bootstrap.Modal.getOrCreateInstance(byId("playground-propose-modal"));
  button.addEventListener("click", async () => {
    byId("playground-propose-copied").textContent = await copyConfiguration(p);
    modal.show();
  });
  byId("playground-propose-open").addEventListener("click", () => modal.hide());
}

// copies the configuration of the organization, returns the message telling whether it has been copied
async function copyConfiguration(p) {
  const {name, jsonnet} = p.organization;
  // with the final new line of the file, trimmed by the playground
  const content = p.organizationDocument.doc.getValue() + (jsonnet.endsWith("\n") ? "\n" : "");
  try {
    await navigator.clipboard.writeText(content);
    return "The configuration of " + name + " has been copied with your changes.";
  } catch (e) {
    return "The configuration could not be copied, copy it from the tab " + name + " of the playground (Ctrl+A, then Ctrl+C).";
  }
}

// the examples collapse to leave the space to the editors, the browser remembering it
function setupCollapsedExamples(p) {
  const layout = document.querySelector(".playground-layout");
  const toggle = byId("playground-examples-toggle");
  const isCollapsed = () => layout.classList.contains(EXAMPLES_COLLAPSED);

  const collapse = (collapsed) => {
    layout.classList.toggle(EXAMPLES_COLLAPSED, collapsed);
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.title = collapsed ? "Show the examples" : "Hide the examples";
    toggle.querySelector("i").className = "fas " + (collapsed ? "fa-angles-right" : "fa-angles-left");
    // the editors take the space left
    p.files.refresh();
    p.output.refresh();
  };
  const switchCollapsed = () => {
    collapse(!isCollapsed());
    remember(EXAMPLES_COLLAPSED, isCollapsed());
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
  } catch (e) {
    // no storage, e.g. in a private window
  }
}

// ---- documents initially opened: the configuration of the organization and the snippet passed in the url,
// otherwise the default snippet

function openDocuments(p) {
  const {documents, organization} = p;
  if (organization !== null) {
    const button = document.querySelector(".playground-example[data-organization]");
    const title = "Current configuration of " + organization.name;
    p.organizationDocument = documents.create("organization", organization.name, title, p.normalize(organization.jsonnet), button);
    documents.add(p.organizationDocument);
  }

  const snippet = snippetDocument(p);
  if (snippet !== null) {
    documents.add(snippet);
  }
  documents.activate(snippet ?? p.organizationDocument);
}

function snippetDocument(p) {
  const snippet = snippetOfHash(window.location.hash);
  if (snippet !== null) {
    return p.documents.create("snippet", MAIN_FILE, "Snippet passed in the link", p.normalize(snippet));
  }
  if (p.organization === null) {
    return p.documents.create("snippet", MAIN_FILE, "Snippet of the playground", p.defaultContent);
  }
  return null;
}
