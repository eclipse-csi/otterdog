import assert from "node:assert/strict";
import {test} from "node:test";

import {distinctImports, encodeSnippet, errorLocations, normalizeSnippet, snippetOfHash} from "./snippets.js";

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

test("only the imports of snippets are mapped to the default configuration, in both quote styles", () => {
  const code = `local orgs = import "vendor/eclipse-defaults/otterdog-defaults.libsonnet";
// import 'vendor/eclipse-defaults/otterdog-defaults.libsonnet'
orgs.newOrg('a', 'b') {
  settings+: {description: "Use import 'vendor/eclipse-defaults/otterdog-defaults.libsonnet'"},
}`;
  assert.equal(
    normalizeSnippet(code, TEMPLATE_FILES, TEMPLATE_FILES[0]),
    code.replace('"vendor/eclipse-defaults/', '"vendor/otterdog-defaults/'),
  );

  // an import being typed, or the text of a string, does not import the default configuration
  for (const code of ["local orgs = import 'vendor/", "{a: \"import 'a.libsonnet'\"}"]) {
    assert.equal(normalizeSnippet(code, TEMPLATE_FILES, TEMPLATE_FILES[0]), `local orgs = import '${TEMPLATE_FILES[0]}';\n\n${code}`);
  }
});

test("opening a snippet keeps explicit imports of upstream libraries", () => {
  /**
   * The selected template has its own defaults and helper. The snippet explicitly
   * imports the upstream versions, which are also available. Opening it must keep
   * those choices instead of silently changing them to the custom libraries.
   */
  const files = [
    "vendor/upstream/otterdog-defaults.libsonnet",
    "vendor/upstream/otterdog-functions.libsonnet",
    "vendor/custom/otterdog-defaults.libsonnet",
    "vendor/custom/otterdog-functions.libsonnet",
  ];
  const code = `local orgs = import 'vendor/upstream/otterdog-defaults.libsonnet';
local helper = import 'vendor/upstream/otterdog-functions.libsonnet';
orgs.newOrg('project', helper.name)`;

  const normalized = normalizeSnippet(code, files, "vendor/custom/otterdog-defaults.libsonnet");

  assert.equal(normalized, code);
});

test("opening a snippet keeps an upstream import containing a current-directory segment", () => {
  /**
   * A user explicitly imports the available upstream defaults with /./ in the
   * path. That spelling names the same file as the listed upstream path. Keep
   * the user's import instead of switching to the selected custom defaults.
   */
  const files = [
    "vendor/upstream/otterdog-defaults.libsonnet",
    "vendor/custom/otterdog-defaults.libsonnet",
  ];
  const code = "import 'vendor/upstream/./otterdog-defaults.libsonnet'";

  const normalized = normalizeSnippet(code, files, "vendor/custom/otterdog-defaults.libsonnet");

  assert.equal(normalized, code);
});

test("opening a snippet keeps an upstream import that goes up to its parent directory", () => {
  /**
   * This import enters upstream/, goes back to vendor/, then enters upstream/
   * again. The target exists, so opening the snippet must preserve its explicit
   * choice of upstream defaults even though custom defaults are also available.
   */
  const files = [
    "vendor/upstream/otterdog-defaults.libsonnet",
    "vendor/custom/otterdog-defaults.libsonnet",
  ];
  const code = "import 'vendor/upstream/../upstream/otterdog-defaults.libsonnet'";

  const normalized = normalizeSnippet(code, files, "vendor/custom/otterdog-defaults.libsonnet");

  assert.equal(normalized, code);
});

test("opening a snippet keeps explicit imports of custom libraries", () => {
  /**
   * Both upstream and custom files are available, with upstream listed first.
   * The snippet already imports the custom defaults and helper. Those exact
   * paths must survive opening the shared URL despite the matching filenames.
   */
  const files = [
    "vendor/upstream/otterdog-defaults.libsonnet",
    "vendor/upstream/otterdog-functions.libsonnet",
    "vendor/custom/otterdog-defaults.libsonnet",
    "vendor/custom/otterdog-functions.libsonnet",
  ];
  const code = `local orgs = import 'vendor/custom/otterdog-defaults.libsonnet';
local helper = import 'vendor/custom/otterdog-functions.libsonnet';
orgs.newOrg('project', helper.name)`;

  const normalized = normalizeSnippet(code, files, "vendor/custom/otterdog-defaults.libsonnet");

  assert.equal(normalized, code);
});

test("a snippet from another project uses the selected custom template and its sibling helper", () => {
  /**
   * The shared URL came from a documentation playground. Its vendor/documentation
   * files do not exist here. Both upstream and custom replacements are available;
   * use the selected custom template and the helper next to it, even though the
   * upstream files appear first in the list.
   */
  const files = [
    "vendor/upstream/otterdog-defaults.libsonnet",
    "vendor/upstream/otterdog-functions.libsonnet",
    "vendor/custom/nested/otterdog-defaults.libsonnet",
    "vendor/custom/nested/otterdog-functions.libsonnet",
  ];
  const code = `local orgs = import 'vendor/documentation/otterdog-defaults.libsonnet';
local helper = import 'vendor/documentation/otterdog-functions.libsonnet';
orgs.newOrg('project', helper.name)`;

  const normalized = normalizeSnippet(code, files, "vendor/custom/nested/otterdog-defaults.libsonnet");

  assert.equal(normalized, `local orgs = import 'vendor/custom/nested/otterdog-defaults.libsonnet';
local helper = import 'vendor/custom/nested/otterdog-functions.libsonnet';
orgs.newOrg('project', helper.name)`);
});

test("a snippet from a nested template in another project uses the selected custom libraries", () => {
  /**
   * The shared URL's template and helper both lived under nested/ in another
   * repository. Those vendor/documentation paths are unavailable here. Treat
   * them like imports from a repository root: use the selected template and
   * its sibling helper, keeping the snippet usable in this playground.
   */
  const files = [
    "vendor/upstream/otterdog-defaults.libsonnet",
    "vendor/upstream/otterdog-functions.libsonnet",
    "vendor/custom/nested/otterdog-defaults.libsonnet",
    "vendor/custom/nested/otterdog-functions.libsonnet",
  ];
  const code = `local orgs = import 'vendor/documentation/nested/otterdog-defaults.libsonnet';
local helper = import 'vendor/documentation/nested/otterdog-functions.libsonnet';
orgs.newOrg('project', helper.name)`;

  const normalized = normalizeSnippet(code, files, "vendor/custom/nested/otterdog-defaults.libsonnet");

  assert.equal(normalized, `local orgs = import 'vendor/custom/nested/otterdog-defaults.libsonnet';
local helper = import 'vendor/custom/nested/otterdog-functions.libsonnet';
orgs.newOrg('project', helper.name)`);
});

test("a shared snippet can reuse an upstream helper when the selected template has no sibling helper", () => {
  /**
   * The snippet imports a helper from another project's vendor directory. This
   * custom template has no helper of its own, but an upstream helper is available.
   * Use that available helper so the snippet's import can be evaluated here.
   */
  const files = [
    "vendor/upstream/otterdog-defaults.libsonnet",
    "vendor/upstream/otterdog-functions.libsonnet",
    "vendor/custom/nested/otterdog-defaults.libsonnet",
  ];
  const code = "import 'vendor/documentation/otterdog-functions.libsonnet'";

  const normalized = normalizeSnippet(code, files, "vendor/custom/nested/otterdog-defaults.libsonnet");

  assert.equal(normalized, "import 'vendor/upstream/otterdog-functions.libsonnet'");
});

test("further imports of a path are spelled differently, strings and comments being kept", () => {
  const files = {
    "playground.jsonnet": `local a = import 'a.libsonnet';
local b = import "a.libsonnet"; // import 'a.libsonnet'
{
  a: "Use import 'a.libsonnet'",
  b: importstr @'a.libsonnet',
  c: |||
    import 'a.libsonnet'
  |||,
}`,
    "a.libsonnet": "{c: import 'a.libsonnet'}",
  };
  assert.deepEqual(distinctImports(files, "playground.jsonnet"), {
    "playground.jsonnet": `local a = import 'a.libsonnet';
local b = import "./a.libsonnet"; // import 'a.libsonnet'
{
  a: "Use import 'a.libsonnet'",
  b: importstr @'././a.libsonnet',
  c: |||
    import 'a.libsonnet'
  |||,
}`,
    "a.libsonnet": "{c: import './././a.libsonnet'}",
  });
});

test("imports of a path spelled with './' are spelled differently too", () => {
  const files = {"playground.jsonnet": "[import 'a.libsonnet', import './a.libsonnet', import 'a.libsonnet', import '././a.libsonnet']"};

  assert.deepEqual(distinctImports(files, "playground.jsonnet"), {
    "playground.jsonnet": "[import 'a.libsonnet', import './a.libsonnet', import '././a.libsonnet', import './././a.libsonnet']",
  });
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
