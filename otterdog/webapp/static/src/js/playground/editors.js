import {defaultKeymap, history, historyKeymap, indentLess, indentMore} from "@codemirror/commands";
import {StreamLanguage, bracketMatching, defaultHighlightStyle, indentUnit, syntaxHighlighting} from "@codemirror/language";
import {lintGutter} from "@codemirror/lint";
import {EditorState, StateEffect, StateField} from "@codemirror/state";
import {Decoration, EditorView, drawSelection, highlightSpecialChars, keymap, lineNumbers} from "@codemirror/view";

// The setup of the CodeMirror editors of the playground: the editor of its documents, the read-only editors of the files
// of the default configuration and of the output.

const KEYWORD = /^(?:assert|else|error|for|function|if|importbin|importstr|import|in|local|self|super|tailstrict|then)\b/;
const ATOM = /^(?:true|false|null)\b/;
const NUMBER = /^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?/;

// The highlighting and the indentation of jsonnet: comments, strings and text blocks, keywords, literals, the names of
// fields and operators. The state follows the comments, strings and text blocks spanning several lines, and the depth
// of the brackets, which lines are indented by.
export const jsonnetParser = {
  name: "jsonnet",
  startState: () => ({comment: false, quote: null, verbatim: false, textBlock: false, depth: 0}),
  token: (stream, state) => (state.comment || state.quote !== null || state.textBlock ? continued(stream, state) : token(stream, state)),
  indent: (state, textAfter, context) => Math.max(0, state.depth - (/^[\]})]/.test(textAfter) ? 1 : 0)) * context.unit,
  languageData: {commentTokens: {line: "//", block: {open: "/*", close: "*/"}}, indentOnInput: /^\s*[\]})]$/},
};

const jsonnet = StreamLanguage.define(jsonnetParser);

function token(stream, state) {
  if (stream.eatSpace()) {
    return null;
  }
  if (stream.match("//") || stream.match("#")) {
    stream.skipToEnd();
    return "comment";
  }
  if (stream.match("/*")) {
    state.comment = true;
    return continued(stream, state);
  }
  if (stream.match("|||")) {
    state.textBlock = true;
    stream.skipToEnd();
    return "string";
  }
  const quote = stream.match(/^@?['"]/);
  if (quote) {
    state.quote = quote[0].slice(-1);
    state.verbatim = quote[0].length > 1;
    return continued(stream, state);
  }
  return bracket(stream, state) ?? word(stream);
}

function bracket(stream, state) {
  if (stream.match(/^[{[(]/)) {
    state.depth++;
    return "bracket";
  }
  if (stream.match(/^[}\])]/)) {
    state.depth = Math.max(0, state.depth - 1);
    return "bracket";
  }
  return null;
}

function word(stream) {
  if (stream.match(ATOM)) {
    return "atom";
  }
  if (stream.match(KEYWORD)) {
    return "keyword";
  }
  if (stream.match(NUMBER)) {
    return "number";
  }
  // the name of a field, e.g. `name:`, `settings+:` or `hidden::`
  if (stream.match(/^[A-Za-z_]\w*(?=\s*\+?:)/)) {
    return "property";
  }
  if (stream.match(/^[A-Za-z_$]\w*/)) {
    return "variable";
  }
  if (stream.match(/^[-+*/%=<>!&|^~]+/)) {
    return "operator";
  }
  stream.next();
  return null;
}

// a comment, a string or a text block continuing on the line
function continued(stream, state) {
  if (state.comment) {
    return blockComment(stream, state);
  }
  return state.textBlock ? textBlock(stream, state) : string(stream, state);
}

function blockComment(stream, state) {
  state.comment = !stream.skipTo("*/");
  if (state.comment) {
    stream.skipToEnd();
  } else {
    stream.pos += 2;
  }
  return "comment";
}

// a text block ends with a line starting with |||
function textBlock(stream, state) {
  if (stream.sol() && stream.match(/^\s*\|\|\|/)) {
    state.textBlock = false;
  } else {
    stream.skipToEnd();
  }
  return "string";
}

// a string ends with its quote, which is escaped with a backslash, or doubled in a verbatim string
function string(stream, state) {
  while (!stream.eol()) {
    const char = stream.next();
    if (char === state.quote && !(state.verbatim && stream.eat(state.quote))) {
      state.quote = null;
      break;
    }
    if (char === "\\" && !state.verbatim) {
      stream.next();
    }
  }
  return "string";
}

// Tab indents the selected lines or inserts an indentation at the cursor, Shift+Tab unindents the lines
const TAB = {
  key: "Tab",
  run: (view) => (view.state.selection.ranges.some((range) => !range.empty) ? indentMore(view) : insertIndentation(view)),
  shift: indentLess,
};

function insertIndentation(view) {
  view.dispatch(view.state.update(view.state.replaceSelection(view.state.facet(indentUnit)), {scrollIntoView: true, userEvent: "input"}));
  return true;
}

const THEME = EditorView.theme({
  "&": {height: "100%", fontSize: "0.8125rem"},
  "&.cm-focused": {outline: "none"},
  ".cm-scroller": {fontFamily: "var(--bs-font-monospace)", overflow: "auto"},
  ".cm-gutters": {backgroundColor: "var(--bs-tertiary-bg)", color: "var(--bs-secondary-color)"},
});

// the extensions of the editors, read-only ones having no history nor indentation keys, and the ones showing no
// diagnostics, e.g. the output, no gutter for them
export function editorExtensions({readOnly = false, diagnostics = true} = {}) {
  return [
    lineNumbers(),
    diagnostics ? lintGutter() : [],
    highlightSpecialChars(),
    drawSelection(),
    bracketMatching(),
    syntaxHighlighting(defaultHighlightStyle, {fallback: true}),
    jsonnet,
    indentUnit.of("  "),
    EditorState.tabSize.of(2),
    THEME,
    readOnly ? EditorState.readOnly.of(true) : [history(), keymap.of([TAB, ...historyKeymap])],
    keymap.of(defaultKeymap),
  ];
}

// Returns marks of the editors, e.g. the matches of a find: the extension of the states, the effect replacing the marks
// with ranges {from, to, className, title}, and the ranges marked in a state, which follow the changes of its document.
export function markField() {
  const set = StateEffect.define();
  const field = StateField.define({
    create: () => Decoration.none,
    update: (marks, transaction) => transaction.effects.reduce(
      (current, effect) => (effect.is(set) ? Decoration.set(effect.value.filter(({from, to}) => from < to).map(markOf), true) : current),
      marks.map(transaction.changes),
    ),
    provide: (f) => EditorView.decorations.from(f),
  });
  return {
    extension: field,
    set: (ranges) => set.of(ranges),
    ranges(state) {
      const ranges = [];
      state.field(field, false)?.between(0, state.doc.length, (from, to) => {
        ranges.push({from, to});
      });
      return ranges;
    },
  };
}

const markOf = ({from, to, className, title}) => Decoration.mark({class: className, attributes: title === undefined ? undefined : {title}}).range(from, to);

// the offset in a document of a position {line, ch} of an error location, see errorLocations
export function offsetOf(doc, {line, ch}) {
  const target = doc.line(Math.min(Math.max(line + 1, 1), doc.lines));
  return Math.min(target.from + ch, target.to);
}

// selects a range of an editor, and scrolls to it
export function select(view, from, to) {
  view.dispatch({selection: {anchor: from, head: to}, effects: EditorView.scrollIntoView(from, {y: "center"})});
  view.focus();
}

// replaces the content of an editor
export const replaceContent = (state, text) => ({changes: {from: 0, to: state.doc.length, insert: text}});
