import {setDiagnostics} from "@codemirror/lint";
import {EditorState} from "@codemirror/state";
import {EditorView} from "@codemirror/view";

import {byId} from "./dom.js";
import {editorExtensions, offsetOf, select} from "./editors.js";
import {importsOf} from "./jsonnet.js";
import {MAIN_FILE, baseName} from "./snippets.js";

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
  const parts = [];
  // Compare filenames after resolving '.' and '..' relative to the importing file.
  for (const part of (directory + path).split("/")) {
    if (part === "..") {
      parts.pop();
    } else if (part !== "." && part !== "") {
      parts.push(part);
    }
  }
  const relativeFilename = parts.join("/");
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

// Returns a function mapping an error location to its editor filename.
// WASM may report only 'helper.libsonnet'. When two libraries share that name,
// the next known caller in the error stack can tell us which one was imported.
// Without that evidence the location stays unlinked, avoiding the wrong editor.
// `location` is an entry from `locations`, the stack parsed by errorLocations().
// Only its file field is needed here; line and column are used later by the editor.
export function fileResolver(templateFiles, editorFilenames) {
  return (location, locations = []) => {
    if (editorFilenames.includes(location.file)) {
      return location.file;
    }
    const matchingFilenames = editorFilenames.filter((name) => name.endsWith("/" + location.file));
    if (matchingFilenames.length === 0) {
      return undefined;
    }
    if (matchingFilenames.length === 1) {
      return matchingFilenames[0];
    }

    // Error locations run from the failure outward through its callers. Only
    // frames after this location can explain how its file was imported.
    const callerLocations = locations.slice(locations.indexOf(location) + 1);
    for (const callerLocation of callerLocations) {
      const caller = templateFiles.find((file) => file.filename === callerLocation.file);
      if (caller === undefined) {
        continue;
      }
      // Repeated frames inside a matching library do not identify its importer.
      if (matchingFilenames.includes(caller.filename)) {
        continue;
      }

      // The caller must actually import the reported path. './' prefixes are
      // equivalent spellings used to distinguish repeated imports in WASM.
      const importsReportedPath = importsOf(caller.content)
        .some(({path}) => path.replace(/^(\.\/)+/, "") === location.file);
      if (!importsReportedPath) {
        return undefined;
      }

      // Resolve relative to this caller, e.g. vendor/custom/defaults.libsonnet
      // importing helper.libsonnet selects vendor/custom/helper.libsonnet.
      // Stop here: more distant callers cannot prove which file this one used.
      const imported = resolveImportedFilename(location.file, caller.filename, templateFiles);
      return matchingFilenames.includes(imported) ? imported : undefined;
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
