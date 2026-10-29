import {setDiagnostics} from "@codemirror/lint";
import {EditorState} from "@codemirror/state";
import {EditorView} from "@codemirror/view";

import {byId} from "./dom.js";
import {editorExtensions, offsetOf, select} from "./editors.js";
import {importsOf} from "./jsonnet.js";
import {MAIN_FILE, baseName} from "./snippets.js";

// The files of the playground: the editor of its documents, and the files of the default configuration shown read-only
// in their own editor, listed in a menu with the files importing them.

// Returns the files importing each file of the default configuration, by name.
export function fileRoles(templateFiles, defaultConfig) {
  const importers = new Map([[defaultConfig, ["the playground"]]]);
  for (const file of templateFiles) {
    for (const imported of importedFiles(file, templateFiles)) {
      importers.set(imported, [...(importers.get(imported) ?? []), baseName(file.filename)]);
    }
  }
  return importers;
}

// Resolve relative imports before the package path/aliases, just as the evaluator does.
function importedFile(path, importer, templateFiles) {
  const relative = importer.slice(0, importer.lastIndexOf("/") + 1) + path;
  const normalized = [];
  for (const part of relative.split("/")) {
    if (part === "..") normalized.pop();
    else if (part !== "." && part !== "") normalized.push(part);
  }
  const owner = (name) => templateFiles.find((file) => file.filename === name)
    ?? templateFiles.find((file) => file.aliases?.includes(name));
  return (owner(normalized.join("/")) ?? owner(path))?.filename;
}

function importedFiles(file, templateFiles) {
  return importsOf(file.content)
    .map(({path}) => importedFile(path, file.filename, templateFiles))
    .filter((imported) => imported !== undefined && imported !== file.filename);
}

// WASM can report only the relative import spelling. If several editors match,
// use the next known stack frame's imports to identify its owner. Ambiguous
// locations stay unresolved rather than marking an unrelated library.
export function fileResolver(templateFiles, filenames) {
  const direct = (name) => filenames.includes(name) ? name
    : templateFiles.find((file) => file.aliases?.includes(name))?.filename;
  return (location, locations = []) => {
    const exact = direct(location.file);
    if (exact !== undefined) return exact;
    const matching = filenames.filter((name) => name.endsWith("/" + location.file));
    if (matching.length === 1) return matching[0];
    for (const frame of locations.slice(locations.indexOf(location) + 1)) {
      const importer = direct(frame.file);
      const file = templateFiles.find((file) => file.filename === importer);
      if (file === undefined) continue;
      if (matching.includes(importer)) continue;
      const candidates = new Set(importsOf(file.content)
        .filter(({path}) => path.replace(/^(\.\/)+/, "") === location.file)
        .map(({path}) => importedFile(path, importer, templateFiles))
        .filter((name) => matching.includes(name)));
      return candidates.size === 1 ? [...candidates][0] : undefined;
    }
    return undefined;
  };
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

  const fileOf = fileResolver(templateFiles, [...files.keys()]);

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
      const filename = fileOf(location, locations);
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
