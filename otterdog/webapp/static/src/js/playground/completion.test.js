import assert from "node:assert/strict";
import {test} from "node:test";

import {functionParameters, propertyInsertion, referenceOf} from "./completion.js";

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

test("custom methods replace packaged signatures without reading calls, strings or comments as definitions", () => {
  const parameters = functionParameters([
    {content: "local newRepo(name) = {};"},
    {content: `{
      // newRepo(fake): {}
      text: 'newRepo(fake): {}',
      value: other.newRepo('argument'),
      newRepo /* method */ ():: {},
      newOrg(name, id=std.join('', ['a', 'b'])): {},
    }`},
  ]);
  assert.deepEqual(Object.fromEntries(parameters), {newRepo: "", newOrg: "name, id=std.join('', ['a', 'b'])"});
});


test("the selected template overrides signatures from libraries that sort after it", () => {
  const files = [
    {filename: "vendor/custom/otterdog-defaults.libsonnet", content: "local upstream = import 'upstream/otterdog-defaults.libsonnet'; local newRepo() = upstream.newRepo('custom'); { newRepo: newRepo }"},
    {filename: "vendor/custom/upstream/otterdog-defaults.libsonnet", content: "local newRepo(name) = {name: name}; local newTeam(name) = {name: name}; { newRepo: newRepo, newTeam: newTeam }"},
  ];
  assert.deepEqual(Object.fromEntries(functionParameters(files, files[0].filename)), {newRepo: "", newTeam: "name"});
});
