import assert from "node:assert/strict";
import {test} from "node:test";

import {functionCompletion, functionParameters, propertyInsertion, referenceOf} from "./completion.js";

const REFERENCE = {
  functions: {newRepo: "repository/index.md"},
  objects: {
    "repository/index.md": {
      title: "Repository",
      properties: {
        has_wiki: {type: "boolean", description: "If the repo has a wiki"},
        workflows: {type: "Workflow Settings", description: "Workflow settings", object: "repository/index.md#workflow-settings"},
      },
    },
    "repository/index.md#workflow-settings": {title: "Workflow Settings", properties: {enabled: {type: "boolean", description: "If enabled"}}},
  },
};

test("the parameters of the functions are read from the default configuration", () => {
  const parameters = functionParameters([{content: "local newRepo(name) = {\n};\nlocal newOrg(name, id=name) = {\n};\nlocal x = 1;"}]);

  assert.deepEqual(Object.fromEntries(parameters), {newRepo: "name", newOrg: "name, id=name"});
});

test("the reference of an object follows the properties of the path", () => {
  assert.equal(referenceOf(REFERENCE, {call: "orgs.newRepo('my-repo')", path: []}).title, "Repository");
  assert.equal(referenceOf(REFERENCE, {call: "orgs.newRepo('my-repo')", path: ["workflows"]}).title, "Workflow Settings");
  assert.equal(referenceOf(REFERENCE, {call: "orgs.newTeam('my-team')", path: []}), null);
});

test("objects and lists are extended, other values are replaced", () => {
  const values = {has_wiki: true, topics: [], workflows: {enabled: true}};

  assert.deepEqual(propertyInsertion("has_wiki", values), {text: "has_wiki: ", cursor: 0});
  assert.deepEqual(propertyInsertion("topics", values), {text: "topics+: []", cursor: -1});
  assert.deepEqual(propertyInsertion("workflows", values), {text: "workflows+: {}", cursor: -1});
  assert.deepEqual(propertyInsertion("_repositories", values), {text: "_repositories+:: ", cursor: 0});
});

// These unit tests supply the evaluator's argument count and the source hint
// explicitly. Browser tests in tests/webapp/playground/test_completion.py check
// that real Jsonnet templates produce those inputs and that completion works in
// the editor.

/**
 * Select the newRepo suggestion in an empty editor and return what the user sees.
 * The fixed alias, constructor and documentation are shared test scaffolding;
 * each test supplies its own parameter hint and evaluated argument count.
 * dispatch captures the edit CodeMirror would apply, while describe returns
 * tooltip data directly instead of rendering browser elements.
 */
function selectRepositoryCompletion({parameterLabel, requiredArguments}) {
  const completion = functionCompletion({
    alias: "orgs",
    name: "newRepo",
    parameterLabel,
    requiredArguments,
    reference: REFERENCE,
    describe: (info) => info,
  });
  let transaction;
  completion.apply({dispatch: (value) => { transaction = value; }}, completion, 0, 0);
  return {
    hint: completion.detail,
    tooltip: completion.info().title,
    insertedText: transaction.changes.insert,
  };
}

test("a custom constructor without parameters is completed without an argument", () => {
  /**
   * The library defines local newRepo(name). The custom template replaces it
   * with the method newRepo(): upstream.newRepo('website').
   * Our name lookup only recognizes local functions, so it still finds 'name'
   * from the library. The evaluator sees the custom method and reports zero
   * required arguments. Selecting the suggestion must therefore insert newRepo().
   */
  const result = selectRepositoryCompletion({parameterLabel: "name", requiredArguments: 0});

  assert.deepEqual(result, {
    hint: "()",
    tooltip: "orgs.newRepo()",
    insertedText: "newRepo()",
  });
});

test("a constructor with an unknown parameter name still offers an argument to fill in", () => {
  /**
   * The template defines newRepo: function(name) { name: name }.
   * Our name lookup does not recognize this form, so no parameter name is known.
   * The evaluator still reports one required argument. The suggestion shows (…)
   * and inserts newRepo(''), letting the user type the repository name.
   */
  const result = selectRepositoryCompletion({parameterLabel: undefined, requiredArguments: 1});

  assert.deepEqual(result, {
    hint: "(…)",
    tooltip: "orgs.newRepo(…)",
    insertedText: "newRepo('')",
  });
});

test("an override requiring an argument is completed with a value even when the template hint is empty", () => {
  /**
   * The template defines local newRepo() with a fixed repository name, so its
   * parameter label is empty. The user overrides it in the playground snippet
   * with newRepo(name). The evaluator now reports one required argument.
   * Selecting the suggestion must insert newRepo('') for the user to fill in.
   */
  const result = selectRepositoryCompletion({parameterLabel: "", requiredArguments: 1});

  assert.deepEqual(result, {
    hint: "(…)",
    tooltip: "orgs.newRepo(…)",
    insertedText: "newRepo('')",
  });
});

test("a constructor with a known name parameter shows the hint and offers a value to fill in", () => {
  /**
   * The template defines local newRepo(name). Both the parameter name and the
   * need for an argument are known. The suggestion shows (name), the tooltip
   * shows orgs.newRepo(name), and selecting it inserts newRepo('') to fill in.
   */
  const result = selectRepositoryCompletion({parameterLabel: "name", requiredArguments: 1});

  assert.deepEqual(result, {
    hint: "(name)",
    tooltip: "orgs.newRepo(name)",
    insertedText: "newRepo('')",
  });
});

test("completion uses the custom template's parameter hints and keeps hints for inherited constructors", () => {
  /**
   * The library provides newRepo(name) and newTeam(name). The custom template
   * replaces only newRepo with a local function that takes no parameters.
   * The hints must show no parameter for newRepo and keep 'name' for newTeam,
   * even though the library file appears after the custom file in this list.
   */
  const files = [
    {
      filename: "vendor/custom/otterdog-defaults.libsonnet",
      content: `local upstream = import 'upstream/otterdog-defaults.libsonnet';
local newRepo() = upstream.newRepo('custom');
upstream + { newRepo: newRepo }`,
    },
    {
      filename: "vendor/custom/upstream/otterdog-defaults.libsonnet",
      content: `local newRepo(name) = {name: name};
local newTeam(name) = {name: name};
{ newRepo: newRepo, newTeam: newTeam }`,
    },
  ];

  const parameters = functionParameters(files, "vendor/custom/otterdog-defaults.libsonnet");

  assert.deepEqual(Object.fromEntries(parameters), {newRepo: "", newTeam: "name"});
});
