import assert from "node:assert/strict";
import {test} from "node:test";

import {encodeSnippet, errorLocations, normalizeSnippet, snippetOfHash} from "./snippets.js";

const TEMPLATE_FILES = [
  "vendor/otterdog-defaults/otterdog-defaults.libsonnet",
  "vendor/otterdog-defaults/otterdog-functions.libsonnet",
];

test("snippets are encoded and decoded, including non ascii characters", () => {
  for (const code of ["orgs.newOrg('a', 'b')", "// é — ✓ 𝄞\n{a: 1}", "x".repeat(100000)]) {
    assert.equal(snippetOfHash("#code=" + encodeSnippet(code)), code);
  }
});

test("only valid snippets are taken from the url", () => {
  assert.equal(snippetOfHash("#code="), null);
  assert.equal(snippetOfHash("#code=" + "A".repeat(200001)), null);
  assert.equal(snippetOfHash("#other"), null);
});

test("snippets import the default configuration", () => {
  assert.equal(
    normalizeSnippet("orgs.newOrg('a', 'b')\n\n", TEMPLATE_FILES, TEMPLATE_FILES[0]),
    "local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';\n\norgs.newOrg('a', 'b')",
  );
  assert.equal(
    normalizeSnippet("local orgs = import 'vendor/eclipse-defaults/otterdog-defaults.libsonnet';\nx", TEMPLATE_FILES, TEMPLATE_FILES[0]),
    "local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';\nx",
  );
});

test("errors are located in the files", () => {
  const message = "RUNTIME ERROR: Missing argument: name\n"
    + "\tplayground.jsonnet:5:5-19\tthunk\n"
    + "\totterdog-functions.libsonnet:2:79-80\tf\n"
    + "\t<std>:1551:37-38\tx\n"
    + "\t./vendor/otterdog-defaults/otterdog-defaults.libsonnet:457:17-64\tobject\n"
    + "\tplayground.jsonnet:(5:8)-(6:13)\tobject\n"
    + "\tplayground.jsonnet:7:3 x";
  const locations = errorLocations(message);

  assert.deepEqual(locations.map((l) => [l.file, l.from, l.to]), [
    ["playground.jsonnet", {line: 4, ch: 4}, {line: 4, ch: 18}],
    ["otterdog-functions.libsonnet", {line: 1, ch: 78}, {line: 1, ch: 79}],
    ["vendor/otterdog-defaults/otterdog-defaults.libsonnet", {line: 456, ch: 16}, {line: 456, ch: 63}],
    ["playground.jsonnet", {line: 4, ch: 7}, {line: 5, ch: 12}],
    ["playground.jsonnet", {line: 6, ch: 2}, {line: 6, ch: 3}],
  ]);
  for (const location of locations) {
    assert.equal(message.slice(location.index, location.index + location.text.length), location.text);
  }
});
