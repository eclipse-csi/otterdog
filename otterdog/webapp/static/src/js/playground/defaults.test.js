import assert from "node:assert/strict";
import {test} from "node:test";

import {defaultsSnippet, removableValues, withoutValues} from "./defaults.js";
import {explicitValues, topLevelLocals} from "./jsonnet.js";

const SNIPPET = `local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';
local newBinaryRepo(name) = orgs.newRepo(name + '-binaries');

orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') {
      allow_merge_commit: true,
      workflows+: {
        enabled: false,
      },
    },
  ],
}`;

test("a snippet compares the values with the default configuration, with the local definitions of the code", () => {
  const snippet = defaultsSnippet(SNIPPET, explicitValues(SNIPPET));

  assert.ok(snippet.startsWith(topLevelLocals(SNIPPET).text + "\n"));
  assert.ok(snippet.includes("  defaultsSame(orgs.newRepo('my-repo'), [\"allow_merge_commit\"], true),"));
  assert.ok(snippet.includes("  defaultsSame(orgs.newRepo('my-repo'), [\"workflows\",\"enabled\"], false),"));
});

test("there is no snippet without value to compare", () => {
  assert.equal(defaultsSnippet("{}", []), null);
});

const CODE = "{a: 1, b: [], c: 3}";
const field = (text) => ({from: CODE.indexOf(text), to: CODE.indexOf(text) + text.length});

test("values are removed from the code with their comma", () => {
  assert.equal(withoutValues(CODE, [field("a: 1")]), "{ b: [], c: 3}");
  assert.equal(withoutValues(CODE, [field("c: 3"), field("a: 1")]), "{ b: [], }");
});

test("only the values that do not change the value of the code once removed can be removed", async () => {
  // the value of the code is the one of its fields, b being computed otherwise in the context of the code
  const evaluated = [];
  const evaluate = async (code) => {
    evaluated.push(code);
    const fields = Object.entries({a: 1, b: [], c: 3}).filter(([name]) => code.includes(name + ":"));
    return JSON.stringify({a: 1, b: ["computed"], c: 3, ...Object.fromEntries(fields)});
  };
  const expected = JSON.stringify({a: 1, b: [], c: 3});

  assert.deepEqual(await removableValues(evaluate, CODE, [field("a: 1"), field("c: 3")], expected), [field("a: 1"), field("c: 3")]);
  assert.equal(evaluated.length, 1, "the values are removed together");
  assert.deepEqual(await removableValues(evaluate, CODE, [field("a: 1"), field("b: []"), field("c: 3")], expected), [field("a: 1"), field("c: 3")]);
});
