// The playground evaluates a configuration with the default configuration of an organization in the browser, the
// content of the playground is not sent to the server, only the evaluated configuration of an organization once asked
// to validate it with otterdog, see validation.js. The page (templates/home/playground.html) renders its markup and
// passes its data to createPlayground, Bootstrap is loaded as vendor script and the editors use CodeMirror.
//
// The modules of playground/ implement the parts of the playground, this module connects them with the controls of
// the page.

import {openLintPanel} from "@codemirror/lint";
import {Transaction} from "@codemirror/state";
import {EditorView} from "@codemirror/view";

import {createChanges} from "./playground/changes.js";
import {completionExtensions} from "./playground/completion.js";
import {createDefaultValues} from "./playground/defaults.js";
import {createDocuments} from "./playground/documents.js";
import {byId, flash, markCurrent} from "./playground/dom.js";
import {editorExtensions, replaceContent, select} from "./playground/editors.js";
import {createEvaluator, createScheduler, filesOf} from "./playground/evaluator.js";
import {setupExamples} from "./playground/examples.js";
import {createFiles} from "./playground/files.js";
import {repositoryCall} from "./playground/jsonnet.js";
import {createOutput, viewId} from "./playground/output.js";
import {
  MAIN_FILE,
  MAX_ENCODED_SNIPPET,
  encodeSnippet,
  errorLocations,
  normalizeSnippet,
  snippetOfHash,
} from "./playground/snippets.js";
import {VALIDATION_LIMITATIONS, createValidation} from "./playground/validation.js";

// delay after the last change typed before evaluating the playground again
const EVALUATION_DELAY = 300;

// the output of a document shown for the first time
const INITIAL_OUTPUT = {view: "", scroll: {left: 0, top: 0}};

export function createPlayground(data) {
  const p = connect(data);
  setupExamples({
    buttons: p.exampleButtons,
    examples: data.examples,
    organization: p.organization,
    open: (button, example) => p.documents.open(button, () => exampleDocument(p, button, example)),
    // the editors take the space left
    onResize: () => {
      p.files.refresh();
      p.output.refresh();
    },
  });
  setupReset(p);
  setupCopyLink(p);
  setupValidation(p);
  setupTemplateChoice(p);
  setupProposal(p);
  openDocuments(p);
}

// creates the parts of the playground, connected through the returned object
function connect(data) {
  const p = {
    data,
    organization: data.organization,
    defaultContent: data.defaultSnippet.trimEnd(),
    normalize: (code) => normalizeSnippet(code, data.templateFiles.map((file) => file.filename), data.defaultConfig),
    exampleButtons: document.querySelectorAll(".playground-example"),
    organizationDocument: null,
    // the evaluation of the current configuration of the organization, see createScheduler
    baseline: null,
    // the view and position of the output to restore once the active document is evaluated
    restoredOutput: null,
  };

  // the editor of the documents, which have its states
  p.editor = new EditorView({parent: byId("playground-editor")});
  p.files = createFiles({
    view: p.editor,
    templateFiles: data.templateFiles,
    defaultConfig: data.defaultConfig,
    onShow: () => p.documents.render(),
  });
  p.output = createOutput(p.files);
  p.confirm = createConfirmation();
  p.evaluate = evaluation(p);
  p.validation = createValidation({
    schemas: data.schemas,
    validationUrl: data.validationUrl,
    documentationUrl: data.documentationUrl,
    dispatch: (d, spec) => p.documents.dispatch(d, spec),
    showProblems: () => openLintPanel(p.editor),
    showNote: (d, key, note) => d === p.documents.active() && p.output.setNote(key, note),
  });
  p.defaultValues = createDefaultValues({
    evaluate: p.evaluate,
    label: data.defaultConfiguration,
    dispatch: (d, spec) => p.documents.dispatch(d, spec),
    goTo: (range) => p.files.goTo(MAIN_FILE, range),
    showNote: (d, note) => d === p.documents.active() && p.output.setNote("defaults", note),
  });
  p.documents = createDocuments({
    view: p.editor,
    extensions: [
      editorExtensions(),
      completionExtensions({
        evaluate: p.evaluate,
        reference: data.reference,
        documentationUrl: data.documentationUrl,
        templateFiles: data.templateFiles,
      }),
      p.defaultValues.extension,
    ],
    isEditorShown: () => p.files.shown() === MAIN_FILE,
    onActivate: (d, previous) => activated(p, d, previous),
    onChange: (update) => changed(p, update),
    confirmClose: (d, close) => p.confirm("Closing the example \"" + d.label + "\" discards your changes to it.", "Close", close),
  });
  p.changes = createChanges({
    name: p.organization?.name,
    showInOutput: (view) => showInOutput(p, view),
    showConfiguration: () => p.documents.activate(p.organizationDocument),
  });
  p.schedule = createScheduler(p.evaluate, {
    current: () => p.documents.active(),
    evaluating: () => p.output.setStatus("evaluating", "Evaluating…"),
    evaluated: (d) => d === p.organizationDocument && organizationEvaluated(p),
    show: (d) => showEvaluation(p, d),
  });
  return p;
}

// the changes typed are evaluated once typing pauses, the other ones, e.g. a reset, at once
function changed(p, update) {
  if (p.documents.update()) {
    updateButtons(p);
  }
  // the changed content is validated once evaluated
  const validate = byId("playground-validate");
  if (validate !== null) {
    validate.disabled = true;
  }
  const typed = update.transactions.some((transaction) => transaction.annotation(Transaction.userEvent) !== undefined);
  p.schedule(typed ? EVALUATION_DELAY : 0);
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
    p.validation.show(d, d.result.value);
    p.defaultValues.highlight(d);
    updateButtons(p);
    return;
  }

  p.validation.clear(d);
  p.defaultValues.clear(d);
  const locations = errorLocations(d.result.error);
  p.files.markErrors(locations, d.result.error.split("\n")[0]);
  p.output.showError(d.result.error, locations);
  updateButtons(p);
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

// the reset of the active document, its validation, and the proposal of the changes to the configuration of the
// organization
function updateButtons(p) {
  const d = p.documents.active();
  const reset = byId("playground-reset");
  reset.disabled = !d.modified;
  reset.title = "Restore " + restoredContentOf(p, d);

  const validate = byId("playground-validate");
  if (validate !== null) {
    // not shown for a snippet, e.g. of a repository, which otterdog does not validate
    validate.classList.toggle("d-none", !p.validation.isOrganization(d));
    const reason = p.validation.reasonNotToValidate(d);
    validate.disabled = reason !== null;
    validate.title = reason ?? VALIDATE_TITLE;
  }

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

// ---- controls of the toolbar

function setupReset(p) {
  byId("playground-reset").addEventListener("click", () => {
    const d = p.documents.active();
    p.confirm("Resetting restores " + restoredContentOf(p, d) + ", your changes will be lost.", "Reset", () => {
      p.documents.dispatch(d, {...replaceContent(d.state, d.original), effects: EditorView.scrollIntoView(0)});
    });
  });
}

function setupCopyLink(p) {
  const button = byId("playground-copy-link");
  button.addEventListener("click", async () => {
    const encoded = encodeSnippet(p.documents.active().code);
    if (encoded.length > MAX_ENCODED_SNIPPET) {
      flash(button, "fa-triangle-exclamation", "Too long for a link");
      return;
    }

    const url = window.location.origin + window.location.pathname + window.location.search + "#code=" + encoded;
    try {
      await navigator.clipboard.writeText(url);
      flash(button, "fa-check", "Link copied");
    } catch {
      // e.g. no clipboard outside of secure contexts
      window.prompt("Copy the link to the playground:", url);
    }
  });
}

const VALIDATE_TITLE = "Validate the configuration with otterdog on the server, like `otterdog validate`.\n"
  + VALIDATION_LIMITATIONS;

// the shown document is validated by otterdog, its problems being shown with the ones of the schemas
function setupValidation(p) {
  const button = byId("playground-validate");
  if (button === null) {
    return;
  }

  button.addEventListener("click", async () => {
    const d = p.documents.active();
    const validated = p.validation.validateWithOtterdog(d);
    updateButtons(p);
    await validated;
    if (d === p.documents.active()) {
      updateButtons(p);
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
  const code = p.documents.active().code;
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
  const content = p.organizationDocument.code + (jsonnet.endsWith("\n") ? "\n" : "");
  try {
    await navigator.clipboard.writeText(content);
    return "The configuration of " + name + " has been copied with your changes.";
  } catch {
    return "The configuration could not be copied, copy it from the tab " + name + " of the playground (Ctrl+A, then Ctrl+C).";
  }
}

// ---- documents: the configuration of the organization and the snippet passed in the url, otherwise the default
// snippet, are initially opened, the examples are opened from their list

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

  // the playground of a project is opened at a repository from its page, e.g. '?repository=my-repo'
  const repository = new URLSearchParams(window.location.search).get("repository");
  if (repository !== null && p.organizationDocument !== null) {
    p.organizationDocument.output = {...INITIAL_OUTPUT, view: viewId("repository", repository)};
  }
  documents.activate(snippet ?? p.organizationDocument);
  if (repository !== null && documents.active() === p.organizationDocument) {
    selectRepository(p, repository);
  }
}

// places the cursor at the call creating a repository in the configuration of the organization, if it is found
function selectRepository(p, name) {
  const call = repositoryCall(p.organizationDocument.code, name);
  if (call !== null) {
    select(p.editor, call.from, call.to);
  }
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

function exampleDocument(p, button, example) {
  return p.documents.create("example", example.label, example.title, p.normalize(example.code), button);
}
