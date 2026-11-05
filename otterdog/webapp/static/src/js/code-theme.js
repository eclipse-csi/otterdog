import {HighlightStyle, syntaxHighlighting} from "@codemirror/language";
import {Compartment} from "@codemirror/state";
import {EditorView, ViewPlugin} from "@codemirror/view";
import {tags} from "@lezer/highlight";

// The colors of the CodeMirror editors (the playground, the impact of the default configuration, the query page) in
// the color mode of the page (data-bs-theme of the html element, set by color-scheme.js).

// the tags of the default highlight style of CodeMirror, its colors read from variables of css/app.scss: the ones of
// CodeMirror on the light background, lighter ones on the dark background
const HIGHLIGHT_STYLE = HighlightStyle.define([
  {tag: tags.meta, color: "var(--otterdog-code-meta)"},
  {tag: tags.link, textDecoration: "underline"},
  {tag: tags.heading, textDecoration: "underline", fontWeight: "bold"},
  {tag: tags.emphasis, fontStyle: "italic"},
  {tag: tags.strong, fontWeight: "bold"},
  {tag: tags.strikethrough, textDecoration: "line-through"},
  {tag: tags.keyword, color: "var(--otterdog-code-keyword)"},
  {tag: [tags.atom, tags.bool, tags.url, tags.contentSeparator, tags.labelName], color: "var(--otterdog-code-atom)"},
  {tag: [tags.literal, tags.inserted], color: "var(--otterdog-code-literal)"},
  {tag: [tags.string, tags.deleted], color: "var(--otterdog-code-string)"},
  {tag: [tags.regexp, tags.escape, tags.special(tags.string)], color: "var(--otterdog-code-escape)"},
  {tag: tags.definition(tags.variableName), color: "var(--otterdog-code-definition)"},
  {tag: tags.local(tags.variableName), color: "var(--otterdog-code-local)"},
  {tag: [tags.typeName, tags.namespace], color: "var(--otterdog-code-type)"},
  {tag: tags.className, color: "var(--otterdog-code-class)"},
  {tag: [tags.special(tags.variableName), tags.macroName], color: "var(--otterdog-code-special)"},
  {tag: tags.definition(tags.propertyName), color: "var(--otterdog-code-property)"},
  {tag: tags.comment, color: "var(--otterdog-code-comment)"},
  {tag: tags.invalid, color: "var(--otterdog-code-invalid)"},
]);

export const HIGHLIGHT_VARIABLES = HIGHLIGHT_STYLE.specs
  .map((spec) => spec.color?.match(/^var\((--[\w-]+)\)$/)?.[1])
  .filter((variable) => variable !== undefined);

const scheme = new Compartment();

function darkTheme() {
  return EditorView.darkTheme.of(document.documentElement.dataset.bsTheme === "dark");
}

// the base theme of CodeMirror (cursor, selection, panels, tooltips) follows the color mode when it changes
const FOLLOW_COLOR_MODE = ViewPlugin.define((view) => {
  const observer = new MutationObserver(() => view.dispatch({effects: scheme.reconfigure(darkTheme())}));
  observer.observe(document.documentElement, {attributes: true, attributeFilter: ["data-bs-theme"]});
  return {destroy: () => observer.disconnect()};
});

// the extensions giving an editor the colors of the color mode of the page
export function codeTheme() {
  return [syntaxHighlighting(HIGHLIGHT_STYLE), scheme.of(darkTheme()), FOLLOW_COLOR_MODE];
}
