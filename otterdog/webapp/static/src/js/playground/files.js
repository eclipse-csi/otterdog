import {setDiagnostics} from "@codemirror/lint";
import {EditorState} from "@codemirror/state";
import {EditorView} from "@codemirror/view";

import {byId} from "./dom.js";
import {editorExtensions, offsetOf, select} from "./editors.js";
import {importsOf} from "./jsonnet.js";
import {MAIN_FILE, baseName, normalizePath} from "./snippets.js";

// The user edits one Jsonnet document. Template libraries are separate read-only
// editors, reachable through the file menu and through links in evaluation errors.
// Keep their full paths: a custom template and an upstream library can each have
// a helper.libsonnet, and opening the wrong one would mislead the user.

// templateFiles contains {filename, content} records. A filename is a full
// browser path, e.g. vendor/custom/nested/helper.libsonnet, not a disk path.
// defaultConfig names the entry file selected by the organization's base_template.
// Return a Map from each imported filename to the names displayed under it in
// the file menu, e.g. "helper.libsonnet — imported by defaults.libsonnet".
export function fileRoles(templateFiles, defaultConfig) {
  const importers = new Map([[defaultConfig, ["the playground"]]]);
  for (const file of templateFiles) {
    for (const imported of importedFiles(file, templateFiles)) {
      importers.set(imported, [...(importers.get(imported) ?? []), baseName(file.filename)]);
    }
  }
  return importers;
}

// Returns the editor filename for an import, or undefined if the file is unavailable.
// For example, importing 'helper.libsonnet' from 'vendor/custom/defaults.libsonnet'
// selects 'vendor/custom/helper.libsonnet', even if another library has that basename.
function resolveImportedFilename(path, importer, templateFiles) {
  const directory = importer.slice(0, importer.lastIndexOf("/") + 1);
  const relativeFilename = normalizePath(directory + path);
  const relativeMatch = templateFiles.find((file) => file.filename === relativeFilename);
  if (relativeMatch !== undefined) {
    return relativeMatch.filename;
  }

  // Imports can also spell a full filename from the browser's file map.
  return templateFiles.find((file) => file.filename === path)?.filename;
}

// The file menu lists actual importing files. Missing imports and self-imports
// do not add an "imported by" entry.
function importedFiles(file, templateFiles) {
  return importsOf(file.content)
    .map(({path}) => resolveImportedFilename(path, file.filename, templateFiles))
    .filter((imported) => imported !== undefined && imported !== file.filename);
}

// Error locations may contain a full path or only a filename. Link a shortened
// path only when it identifies one editor; the caller's imports do not prove
// where a failing function was defined. Ambiguous locations stay unlinked.
export function fileResolver(editorFilenames) {
  return (location) => {
    if (editorFilenames.includes(location.file)) {
      return location.file;
    }
    const matchingFilenames = editorFilenames.filter((name) => name.endsWith("/" + location.file));
    return matchingFilenames.length === 1 ? matchingFilenames[0] : undefined;
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

  const fileOf = fileResolver([...files.keys()]);

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
