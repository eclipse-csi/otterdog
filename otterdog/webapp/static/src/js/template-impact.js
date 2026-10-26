// The impact of a change of the default configuration of the instance on its projects: the files of the default
// configuration are edited in the browser, and the configurations of the projects are evaluated with them, see
// playground/impact.js. The page (templates/home/template-impact.html) renders its markup and passes its data to
// createTemplateImpact, Bootstrap is loaded as vendor script.

import {EditorState} from "@codemirror/state";
import {EditorView} from "@codemirror/view";

import {editorExtensions, replaceContent} from "./playground/editors.js";
import {createEvaluator} from "./playground/evaluator.js";
import {createImpact} from "./playground/impact.js";
import {normalizeSnippet} from "./playground/snippets.js";

export function createTemplateImpact(data) {
  const files = createTemplateEditors(data.templateFiles, () => update());
  const update = createImpact({
    url: data.configurationsUrl,
    createEvaluator,
    normalize: (code) => normalizeSnippet(code, data.templateFiles.map((file) => file.filename), data.defaultConfig),
    published: data.templateFiles,
    isEdited: files.isEdited,
    edited: files.contents,
    revision: files.revision,
  });
}

// Creates the editors of the files of the default configuration, one in each tab, onChange being called once they
// changed. Returns whether they have been edited, their contents {filename, content}, and their revision.
function createTemplateEditors(templateFiles, onChange) {
  const editors = new Map();
  let revision = 0;

  const isModified = (filename) => editors.get(filename).view.state.doc.toString() !== editors.get(filename).original;

  function changed() {
    revision++;
    for (const [filename, {pane, tab}] of editors) {
      pane.querySelector(".playground-file-restore").classList.toggle("d-none", !isModified(filename));
      tab.querySelector(".playground-document-modified").classList.toggle("d-none", !isModified(filename));
    }
    onChange();
  }

  for (const pane of document.querySelectorAll(".tab-pane[data-file]")) {
    const {filename, content} = templateFiles.find((file) => file.filename === pane.dataset.file);
    const extensions = [editorExtensions(), EditorView.updateListener.of((update) => update.docChanged && changed())];
    const view = new EditorView({parent: pane.querySelector(".playground-code"), state: EditorState.create({doc: content, extensions})});
    const tab = document.querySelector(`[data-bs-target="#${pane.id}"]`);
    editors.set(filename, {view, pane, tab, original: content});

    pane.querySelector(".playground-file-restore").addEventListener("click", (event) => {
      event.preventDefault();
      view.dispatch(replaceContent(view.state, content));
    });
    // editors in hidden tabs are laid out once shown
    tab.addEventListener("shown.bs.tab", () => view.requestMeasure());
  }

  return {
    isEdited: () => [...editors.keys()].some(isModified),
    contents: () => templateFiles.map(({filename}) => ({filename, content: editors.get(filename).view.state.doc.toString()})),
    revision: () => revision,
  };
}
