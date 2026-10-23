import {byId} from "./dom.js";

const MAX_MATCHES = 10000;
const MAX_MARKS = 1000;

// Finds a text in the output, ignoring the case, Enter and Shift+Enter going to the next and previous match.
export function createFind(editor) {
  const input = byId("playground-output-find");
  const count = byId("playground-output-find-count");
  const previous = byId("playground-output-find-previous");
  const next = byId("playground-output-find-next");

  let matches = [];
  let current = -1;
  let marks = [];
  let currentMark = null;

  // finds the text again, e.g. in a new output, scrolling to the current match if asked
  function update(scroll) {
    editor.operation(() => {
      marks.forEach((mark) => mark.clear());
      matches = matchesOf(editor, input.value.toLowerCase());
      marks = matches.slice(0, MAX_MARKS).map((match) => editor.markText(match.from, match.to, {className: "playground-find-match"}));
    });
    current = matches.length === 0 ? -1 : Math.min(Math.max(current, 0), matches.length - 1);
    showCurrent(scroll);
  }

  function showCurrent(scroll) {
    currentMark?.clear();
    currentMark = null;
    if (current >= 0) {
      const {from, to} = matches[current];
      currentMark = editor.markText(from, to, {className: "playground-find-current"});
      if (scroll) {
        editor.scrollIntoView({from, to}, 50);
      }
    }
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

function matchesOf(editor, term) {
  const matches = [];
  if (term === "") {
    return matches;
  }

  let line = 0;
  editor.eachLine((handle) => {
    const text = handle.text.toLowerCase();
    for (let ch = text.indexOf(term); ch !== -1 && matches.length < MAX_MATCHES; ch = text.indexOf(term, ch + term.length)) {
      matches.push({from: {line, ch}, to: {line, ch: ch + term.length}});
    }
    line++;
  });
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
