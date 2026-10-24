import assert from "node:assert/strict";
import {test} from "node:test";

import {aggregateChanges, impactOf, mapConcurrently} from "./impact.js";
import {diffConfigurations} from "./diff.js";

test("each runner runs one task at a time, the results keep the order of the items", async () => {
  const running = new Set();
  let concurrent = 0;
  const results = await mapConcurrently([1, 2, 3, 4, 5], ["a", "b"], async (runner, item) => {
    assert.ok(!running.has(runner), "a runner runs one task at a time");
    running.add(runner);
    concurrent = Math.max(concurrent, running.size);
    await new Promise((resolve) => setTimeout(resolve, 6 - item));
    running.delete(runner);
    return item * 10;
  });

  assert.deepEqual(results, [10, 20, 30, 40, 50]);
  assert.equal(concurrent, 2);
});

test("the impact of the edited default configuration on a project", () => {
  const configuration = {repositories: [{name: "a", has_wiki: true}]};
  const edited = {repositories: [{name: "a", has_wiki: false}]};

  assert.deepEqual(impactOf("p", {value: configuration}, {value: configuration}), {name: "p", kind: "unchanged", changes: []});
  const changed = impactOf("p", {value: configuration}, {value: edited});
  assert.equal(changed.kind, "changed");
  assert.deepEqual(changed.changes.map((change) => change.path), ["repositories[a].has_wiki"]);
  assert.deepEqual(impactOf("p", {value: configuration}, {error: "boom"}), {name: "p", kind: "failing", error: "boom"});
  // a project failing with the published default configuration is not blamed on the edited one
  assert.deepEqual(impactOf("p", {error: "broken"}, {error: "boom"}), {name: "p", kind: "broken", error: "broken"});
});

test("a project that the evaluator failed to evaluate is not blamed on the default configuration", () => {
  const failed = {error: "the evaluator failed: out of memory", failed: true};

  assert.deepEqual(impactOf("p", {value: {}}, failed), {name: "p", kind: "unevaluated", error: failed.error});
  assert.deepEqual(impactOf("p", failed, {value: {}}), {name: "p", kind: "unevaluated", error: failed.error});
});

test("the changes of the projects are grouped by property and values", () => {
  const before = {repositories: [{name: "a", has_wiki: true, rulesets: []}, {name: "b", has_wiki: true, rulesets: []}]};
  const after = {
    repositories: [
      {name: "a", has_wiki: false, rulesets: [{name: "main", enforcement: "active"}]},
      {name: "b", has_wiki: false, rulesets: [{name: "release", enforcement: "active"}]},
    ],
  };
  const impacts = [
    {name: "p1", changes: diffConfigurations(before, after)},
    {name: "p2", changes: diffConfigurations({repositories: [before.repositories[0]]}, {repositories: [after.repositories[0]]})},
    {name: "p3", changes: diffConfigurations({settings: {name: "x"}}, {settings: {name: "y"}})},
  ];

  const groups = aggregateChanges(impacts).map(({pattern, change, count, projects}) => [change.type, pattern, count, projects]);

  assert.deepEqual(groups, [
    ["changed", "repositories[*].has_wiki", 3, ["p1", "p2"]],
    // objects added are grouped whatever their values
    ["added", "repositories[*].rulesets[*]", 3, ["p1", "p2"]],
    ["changed", "settings.name", 1, ["p3"]],
  ]);
});
