import {setDiagnostics} from "@codemirror/lint";
import {EditorState} from "@codemirror/state";
import {EditorView} from "@codemirror/view";

import {byId} from "./dom.js";
import {editorExtensions, offsetOf, select} from "./editors.js";
import {MAIN_FILE, baseName} from "./snippets.js";

// The files of the playground: the editor of its documents, and the files of the default configuration shown read-only
// in their own editor, listed in a menu with the files importing them.

// Returns the files importing each file of the default configuration, by name.
export function fileRoles(templateFiles, defaultConfig) {
  const importers = new Map([[defaultConfig, ["the playground"]]]);
  for (const file of templateFiles) {
    for (const imported of importsOf(file, templateFiles)) {
      importers.set(imported, [...(importers.get(imported) ?? []), baseName(file.filename)]);
    }
  }
  return importers;
}

// the files of the default configuration imported by one of them, matched by their name
function importsOf(file, templateFiles) {
  return [...file.content.matchAll(/\bimport(?:str|bin)?\s*['"]([^'"]+)['"]/g)]
    .map((match) => templateFiles.find((other) => baseName(other.filename) === baseName(match[1]))?.filename)
    .filter((imported) => imported !== undefined && imported !== file.filename);
}

// Creates the editors of the files, the editor of the documents being the one of the main file, onShow being called
// once another file is shown.
export function createFiles({view, templateFiles, defaultConfig, onShow}) {
  const toggle = byId("playground-files-toggle");
  const label = byId("playground-files-label");
  const errorSign = toggle.querySelector(".playground-files-error");
  const items = document.querySelectorAll(".playground-file-item");

  const files = new Map();
  for (const pane of document.querySelectorAll(".tab-pane[data-file]")) {
    const template = templateFiles.find((file) => file.filename === pane.dataset.file);
    const fileView = template === undefined
      ? view
      : new EditorView({
        parent: pane.querySelector(".playground-code"),
        state: EditorState.create({doc: template.content, extensions: editorExtensions({readOnly: true})}),
      });
    files.set(pane.dataset.file, {view: fileView, pane});
  }
  showRoles(fileRoles(templateFiles, defaultConfig));

  let shown = MAIN_FILE;

  function show(filename) {
    shown = filename;
    for (const [name, file] of files) {
      file.pane.classList.toggle("active", name === filename);
    }
    for (const item of items) {
      item.classList.toggle("active", item.dataset.file === filename);
    }
    toggle.classList.toggle("active", filename !== MAIN_FILE);
    label.textContent = filename === MAIN_FILE ? "Default configuration" : baseName(filename);
    onShow();
    // editors in hidden panes are laid out once shown
    files.get(filename).view.requestMeasure();
  }

  // locations of errors may only have the name of a file, e.g. a file imported by the default configuration
  function fileOf(location) {
    if (files.has(location.file)) {
      return location.file;
    }
    const matching = [...files.keys()].filter((name) => name.endsWith("/" + location.file));
    return matching.length === 1 ? matching[0] : undefined;
  }

  // shows a range {from, to} of a file, of offsets or of the positions {line, ch} of an error location
  function goTo(filename, location) {
    show(filename);
    const fileView = files.get(filename).view;
    const [from, to] = [location.from, location.to].map((position) => offsetOfPosition(fileView.state.doc, position));
    select(fileView, from, to);
  }

  // reports an error at its first location in each file, the closest one to the error
  function markErrors(locations, message) {
    clearErrors();
    const marked = new Set();
    for (const location of locations) {
      const filename = fileOf(location);
      if (filename !== undefined && !marked.has(filename)) {
        marked.add(filename);
        const fileView = files.get(filename).view;
        const [from, to] = [location.from, location.to].map((position) => offsetOf(fileView.state.doc, position));
        fileView.dispatch(setDiagnostics(fileView.state, [{from, to, severity: "error", source: "jsonnet", message}]));
      }
    }
    errorSign.classList.toggle("d-none", ![...marked].some((filename) => filename !== MAIN_FILE));
  }

  function clearErrors() {
    for (const {view: fileView} of files.values()) {
      fileView.dispatch(setDiagnostics(fileView.state, []));
    }
    errorSign.classList.add("d-none");
  }

  for (const item of items) {
    item.addEventListener("click", () => show(item.dataset.file));
  }

  return {
    show,
    shown: () => shown,
    fileOf,
    goTo,
    markErrors,
    clearErrors,
    refresh: () => files.get(shown).view.requestMeasure(),
  };
}

const offsetOfPosition = (doc, position) => (typeof position === "number" ? position : offsetOf(doc, position));

function showRoles(roles) {
  for (const element of document.querySelectorAll(".playground-file-role")) {
    const importers = roles.get(element.closest("[data-file]").dataset.file);
    element.textContent = importers === undefined ? "" : "imported by " + importers.join(", ");
  }
}
