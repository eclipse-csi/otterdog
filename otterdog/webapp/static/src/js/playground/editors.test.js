import {StringStream} from "@codemirror/language";
import assert from "node:assert/strict";
import {test} from "node:test";

import {jsonnetParser} from "./editors.js";

// the tokens of the lines of a code, as [text, style] without the spaces, and the state at its end
function tokensOf(code) {
  const state = jsonnetParser.startState();
  const tokens = [];
  for (const line of code.split("\n")) {
    const stream = new StringStream(line, 2, 2);
    while (!stream.eol()) {
      const style = jsonnetParser.token(stream, state);
      if (stream.current().trim() !== "") {
        tokens.push([stream.current(), style]);
      }
      stream.start = stream.pos;
    }
  }
  return {tokens, state};
}

test("jsonnet is highlighted", () => {
  const {tokens} = tokensOf("local orgs = import 'a.libsonnet'; // the default configuration\n{ name+: \"it's\", n: 1.5e2, b: true }");

  assert.deepEqual(tokens, [
    ["local", "keyword"], ["orgs", "variable"], ["=", "operator"], ["import", "keyword"], ["'a.libsonnet'", "string"],
    [";", null], ["// the default configuration", "comment"],
    ["{", "bracket"], ["name", "property"], ["+", "operator"], [":", null], ["\"it's\"", "string"], [",", null],
    ["n", "property"], [":", null], ["1.5e2", "number"], [",", null], ["b", "property"], [":", null], ["true", "atom"], ["}", "bracket"],
  ]);
});

test("comments, strings and text blocks may span several lines", () => {
  const {tokens, state} = tokensOf("/* a\nb */ x: |||\n  text: { not code\n|||, y: @'it''s'");

  assert.deepEqual(tokens.map(([, style]) => style), ["comment", "comment", "property", null, "string", "string", "string", null, "property", null, "string"]);
  assert.equal(tokens[tokens.length - 1][0], "@'it''s'");
  assert.deepEqual({comment: state.comment, quote: state.quote, textBlock: state.textBlock}, {comment: false, quote: null, textBlock: false});
});

test("lines are indented by the depth of the brackets", () => {
  const {state} = tokensOf("orgs.newOrg('p', 'o') {\n  settings+: {");
  const context = {unit: 2};

  assert.equal(jsonnetParser.indent(state, "name: 'x',", context), 4);
  assert.equal(jsonnetParser.indent(state, "},", context), 2);
});
