import {byId, element, icon} from "./dom.js";

const ICONS = {organization: "fa-building", snippet: "fa-file-code", example: "fa-book-open"};

// The documents of the playground: the configuration of the organization, the snippet and the opened examples, each
// one keeping its changes, history and evaluation. They share the editor of the playground, which shows the active one.
// An example opened as preview is replaced by the next one opened, unless it was modified.
//
// isEditorShown tells whether the editor is shown rather than a file of the default configuration, onActivate is
// called with the activated document and the previous one, confirmClose with a modified example and its closing.
export function createDocuments({editor, isEditorShown, onActivate, confirmClose}) {
  const {CodeMirror} = window;
  const tabs = byId("playground-documents");
  const documents = [];
  let active = null;

  function create(kind, label, title, content, button = null) {
    return {
      kind,
      label,
      title,
      original: content,
      doc: new CodeMirror.Doc(content, "jsonnet"),
      // the button of the document in the list of examples
      button,
      preview: kind === "example",
      modified: false,
      // the last evaluation, see createScheduler
      result: null,
      // the view and position of the output, restored once the document is shown again
      output: null,
    };
  }

  function render() {
    const actions = {activate, close};
    tabs.replaceChildren(...documents.map((d) => tabOf(d, d === active && isEditorShown(), actions)));
    tabs.querySelector(".nav-link.active")?.scrollIntoView({block: "nearest", inline: "nearest"});
  }

  function activate(d) {
    const previous = active;
    if (previous !== d) {
      active = d;
      editor.swapDoc(d.doc);
    }
    onActivate(d, previous);
  }

  // activates the document of a button of the list of examples, opening it in place of the preview if needed
  function open(button, createDocument) {
    const opened = documents.find((d) => d.button === button);
    if (opened !== undefined) {
      activate(opened);
      return;
    }

    const d = createDocument();
    const preview = documents.findIndex((other) => other.preview);
    if (preview === -1) {
      documents.push(d);
    } else {
      documents[preview] = d;
    }
    activate(d);
  }

  function close(d) {
    const remove = () => {
      const index = documents.indexOf(d);
      documents.splice(index, 1);
      if (d === active) {
        activate(documents[Math.max(0, index - 1)]);
      } else {
        render();
      }
    };
    if (d.modified) {
      confirmClose(d, remove);
    } else {
      remove();
    }
  }

  // follows the changes of the active document, returns whether it became modified or unmodified
  function update() {
    const modified = active.doc.getValue() !== active.original;
    // a modified example is kept open, also once its changes are undone
    const preview = active.preview && !modified;
    const changed = modified !== active.modified || preview !== active.preview;
    Object.assign(active, {modified, preview});
    if (changed) {
      render();
    }
    return changed;
  }

  return {
    create,
    add: (d) => documents.push(d),
    activate,
    open,
    update,
    render,
    active: () => active,
    // whether a document other than the active one has been modified
    othersModified: () => documents.some((d) => d !== active && d.modified),
  };
}

function tabOf(d, selected, {activate, close}) {
  const item = element("li", "nav-item playground-document");
  item.classList.toggle("playground-document-preview", d.preview);
  item.classList.toggle("playground-document-closable", d.kind === "example");
  item.setAttribute("role", "presentation");
  item.append(tabButton(d, selected, activate));
  if (d.kind === "example") {
    item.append(closeButton(d, close));
  }
  return item;
}

function tabButton(d, selected, activate) {
  const tab = element("button", "nav-link");
  tab.type = "button";
  tab.classList.toggle("active", selected);
  tab.setAttribute("role", "tab");
  tab.setAttribute("aria-selected", String(selected));
  tab.title = d.title + (d.preview ? " (preview, replaced by the next example opened unless modified)" : "");
  tab.append(icon("fas fa-xs " + ICONS[d.kind]), element("span", "playground-document-label", d.label));
  if (d.modified) {
    const modified = element("span", "playground-document-modified", "●");
    modified.title = "Modified";
    tab.append(modified);
  }
  tab.addEventListener("click", () => activate(d));
  return tab;
}

function closeButton(d, close) {
  const button = element("button", "btn-close playground-document-close");
  button.type = "button";
  button.title = "Close";
  button.setAttribute("aria-label", "Close " + d.label);
  button.addEventListener("click", () => close(d));
  return button;
}
