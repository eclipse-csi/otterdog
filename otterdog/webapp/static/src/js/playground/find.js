import {SearchCursor} from "@codemirror/search";
import {EditorView} from "@codemirror/view";

import {byId} from "./dom.js";

const MAX_MATCHES = 10000;
const MAX_MARKS = 1000;

// Finds a text in the output, ignoring the case, Enter and Shift+Enter going to the next and previous match. The
// matches are marked with marks, see markField, which the state of the editor of the output must have.
export function createFind(view, marks) {
  const input = byId("playground-output-find");
  const count = byId("playground-output-find-count");
  const previous = byId("playground-output-find-previous");
  const next = byId("playground-output-find-next");

  let matches = [];
  let current = -1;

  // finds the text again, e.g. in a new output, scrolling to the current match if asked
  function update(scroll) {
    matches = matchesOf(view.state.doc, input.value.toLowerCase());
    current = matches.length === 0 ? -1 : Math.min(Math.max(current, 0), matches.length - 1);
    showCurrent(scroll);
  }

  // marks the matches, the current one apart so that it stands out
  function showCurrent(scroll) {
    const ranges = matches.slice(0, MAX_MARKS).filter((match, index) => index !== current)
      .map(({from, to}) => ({from, to, className: "playground-find-match"}));
    const effects = [marks.set(current < 0 ? ranges : [...ranges, {...matches[current], className: "playground-find-current"}])];
    if (scroll && current >= 0) {
      effects.push(EditorView.scrollIntoView(matches[current].from, {y: "center"}));
    }
    view.dispatch({effects});
    count.textContent = countText(input.value, matches.length, current);
    previous.disabled = next.disabled = matches.length === 0;
  }

  function move(step) {
    if (matches.length > 0) {
      current = (current + step + matches.length) % matches.length;
      showCurrent(true);
    }
  }

  input.addEventListener("input", () => {
    current = 0;
    update(true);
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      move(event.shiftKey ? -1 : 1);
    }
  });
  previous.addEventListener("click", () => move(-1));
  next.addEventListener("click", () => move(1));

  return {
    update,
    focus: () => input.focus(),
    // disabled while the output shows an error
    setEnabled(enabled) {
      input.disabled = !enabled;
      previous.disabled = next.disabled = !enabled || matches.length === 0;
    },
  };
}

function matchesOf(doc, term) {
  const matches = [];
  if (term === "") {
    return matches;
  }

  const cursor = new SearchCursor(doc, term, 0, doc.length, (text) => text.toLowerCase());
  while (matches.length < MAX_MATCHES && !cursor.next().done) {
    matches.push({from: cursor.value.from, to: cursor.value.to});
  }
  return matches;
}

function countText(term, total, current) {
  if (term === "") {
    return "";
  }
  if (total === 0) {
    return "No match";
  }
  return (current + 1) + "/" + total + (total >= MAX_MATCHES ? "+" : "");
}
