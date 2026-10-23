import {MAIN_FILE, baseName} from "./snippets.js";
import {isObject} from "./diff.js";
import {actionLink, byId, element} from "./dom.js";
import {createFind} from "./find.js";

// the views of the output besides the whole output: the sections of the configuration and its repositories
const VIEWS = [["Sections", "section:"], ["Repositories", "repository:"]];

// The output of the shown document: its evaluation, possibly restricted to a section of the configuration or to a
// repository, or its error, whose locations lead to the corresponding lines of the files.
export function createOutput(files) {
  const {CodeMirror} = window;
  const area = byId("playground-output");
  const errorPanel = byId("playground-error");
  const status = byId("playground-status");
  const viewSelect = byId("playground-output-view");

  const editor = CodeMirror(area, {
    mode: "jsonnet",
    lineNumbers: true,
    readOnly: true,
    tabSize: 2,
    scrollbarStyle: "native",
    extraKeys: {
      "Ctrl-F": () => find.focus(),
      "Cmd-F": () => find.focus(),
    },
  });
  const find = createFind(editor);

  // the shown evaluation, null while an error is shown
  let value = null;
  let viewsSignature = null;
  let shownView = null;

  function setStatus(state, text, action) {
    status.dataset.state = state;
    status.classList.toggle("text-danger", state === "error");
    status.classList.toggle("text-secondary", state !== "error");
    status.replaceChildren(...statusContent(state, text, action));
  }

  function updateViews() {
    const views = viewsOf(value);
    const signature = JSON.stringify(views);
    if (signature !== viewsSignature) {
      viewsSignature = signature;
      const selected = viewSelect.value;
      viewSelect.replaceChildren(new Option("Whole output", ""), ...optionGroups(views));
      selectView(selected);
    }
  }

  function selectView(view) {
    viewSelect.value = view;
    if (viewSelect.value !== view) {
      viewSelect.value = "";
    }
  }

  // renders the output at the given position, by default at the same position if the view did not change
  function render(scroll) {
    const kept = shownView === viewSelect.value ? editor.getScrollInfo() : undefined;
    const text = JSON.stringify(viewOf(value, viewSelect.value), null, 2);
    if (text !== editor.getValue()) {
      editor.setValue(text);
    }
    const position = scroll ?? kept;
    if (position !== undefined) {
      editor.scrollTo(position.left, position.top);
    }
    shownView = viewSelect.value;
    find.update(false);
  }

  // shows the output or the error panel
  function showPanel(output) {
    area.classList.toggle("d-none", !output);
    errorPanel.classList.toggle("d-none", output);
    viewSelect.disabled = !output;
    find.setEnabled(output);
  }

  // shows an evaluation, at the view and position of the document if it has just been shown again
  function showValue(evaluation, duration, restored) {
    value = evaluation;
    showPanel(true);
    editor.refresh();
    updateViews();
    if (restored !== null) {
      selectView(restored.view);
    }
    render(restored?.scroll);
    setStatus("ok", "Evaluated in " + Math.round(duration) + " ms");
  }

  function showError(message, locations) {
    value = null;
    errorPanel.querySelector("pre").replaceChildren(...errorContent(message, locations, files));
    showPanel(false);
    setStatus("error", ...errorStatus(locations, files));
  }

  // the output is laid out once shown, e.g. after showing the changes
  byId("playground-output-tab").addEventListener("shown.bs.tab", () => editor.refresh());
  viewSelect.addEventListener("change", () => {
    if (value !== null) {
      render();
    }
  });

  return {
    setStatus,
    // a note after the status, e.g. about the values of the shown document
    setNote(note) {
      status.querySelector(".playground-status-note")?.remove();
      if (note !== null) {
        const wrapper = element("span", "playground-status-note");
        wrapper.append(" · ", note);
        status.append(wrapper);
      }
    },
    showValue,
    showError,
    // the view and position of the output, restored once its document is shown again
    state: () => (value === null ? null : {view: viewSelect.value, scroll: editor.getScrollInfo()}),
    show(view) {
      selectView(view);
      render({left: 0, top: 0});
    },
    refresh: () => editor.refresh(),
  };
}

// the names of the sections of a configuration and of its repositories, in the order of VIEWS
function viewsOf(value) {
  if (!isObject(value)) {
    return [[], []];
  }
  const sections = Object.keys(value).filter((key) => value[key] !== null && typeof value[key] === "object");
  const repositories = Array.isArray(value.repositories) ? value.repositories : [];
  return [sections, repositories.map((repository) => repository?.name).filter((name) => typeof name === "string")];
}

function optionGroups(views) {
  return VIEWS.map(([label, prefix], index) => {
    const group = element("optgroup");
    group.label = label;
    group.append(...views[index].map((name) => new Option(name, prefix + name)));
    return group;
  }).filter((group) => group.children.length > 0);
}

function viewOf(value, view) {
  if (view.startsWith("section:")) {
    return value[view.slice("section:".length)];
  }
  if (view.startsWith("repository:")) {
    return value.repositories.find((repository) => repository?.name === view.slice("repository:".length));
  }
  return value;
}

function statusContent(state, text, action) {
  const content = action === undefined ? text : actionLink(text, "link-danger", action);
  if (state !== "evaluating") {
    return [content];
  }
  const spinner = element("span", "spinner-border spinner-border-sm me-1");
  spinner.setAttribute("aria-hidden", "true");
  return [spinner, content];
}

// the message of an error, its locations leading to the corresponding lines
function errorContent(message, locations, files) {
  const content = [];
  let index = 0;
  for (const location of locations) {
    const filename = files.fileOf(location);
    const text = filename === undefined
      ? location.text
      : actionLink(location.text, "link-danger", () => files.goTo(filename, location));
    content.push(message.slice(index, location.index), text);
    index = location.index + location.text.length;
  }
  content.push(message.slice(index).replace(/\s+$/, ""));
  return content;
}

// the status of an error: its first location in a file of the playground, leading to it
function errorStatus(locations, files) {
  const first = locations.find((location) => files.fileOf(location) !== undefined);
  if (first === undefined) {
    return ["Error"];
  }
  const filename = files.fileOf(first);
  const where = filename === MAIN_FILE ? "Error at line " : "Error in " + baseName(filename) + ", line ";
  return [where + (first.from.line + 1), () => files.goTo(filename, first)];
}
