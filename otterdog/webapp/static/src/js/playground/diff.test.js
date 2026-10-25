import assert from "node:assert/strict";
import {test} from "node:test";

import {changeCount, changeTree, diffConfigurations, patternOf} from "./diff.js";

const BEFORE = {
  settings: {name: "x", web_commit_signoff_required: false},
  webhooks: [{url: "https://a.example.org", events: ["push"]}],
  repositories: [
    {
      name: "a",
      has_wiki: true,
      topics: ["x", "y"],
      rulesets: [],
      branch_protection_rules: [{pattern: "main", required_approving_review_count: 1}],
    },
    {name: "b", has_wiki: true, topics: [], rulesets: []},
  ],
};

function after() {
  const result = structuredClone(BEFORE);
  result.settings.web_commit_signoff_required = true;
  result.repositories[0].has_wiki = false;
  result.repositories[0].topics = ["y", "z"];
  result.repositories[0].rulesets.push({name: "main", enforcement: "active"});
  result.repositories[0].branch_protection_rules[0].required_approving_review_count = 2;
  result.repositories.splice(1, 1);
  result.repositories.push({name: "c"});
  result.webhooks[0].events = ["push", "pull_request"];
  return result;
}

const summaryOf = (change) => [change.type, change.path, change.before ?? change.value, change.after];

test("changes are matched by property and by element of lists", () => {
  assert.deepEqual(diffConfigurations(BEFORE, after()).map(summaryOf), [
    ["changed", "settings.web_commit_signoff_required", false, true],
    ["added", "webhooks[https://a.example.org].events[]", "pull_request", undefined],
    ["changed", "repositories[a].has_wiki", true, false],
    ["added", "repositories[a].topics[]", "z", undefined],
    ["removed", "repositories[a].topics[]", "x", undefined],
    ["added", "repositories[a].rulesets[main]", {name: "main", enforcement: "active"}, undefined],
    ["changed", "repositories[a].branch_protection_rules[main].required_approving_review_count", 1, 2],
    ["added", "repositories[c]", {name: "c"}, undefined],
    ["removed", "repositories[b]", BEFORE.repositories[1], undefined],
  ]);
});

test("equal configurations have no change", () => {
  assert.deepEqual(diffConfigurations(BEFORE, structuredClone(BEFORE)), []);
});

test("a different order of values is a change of the list", () => {
  assert.deepEqual(diffConfigurations({t: ["a", "b"]}, {t: ["b", "a"]}).map(summaryOf), [
    ["changed", "t", ["a", "b"], ["b", "a"]],
  ]);
});

test("elements of lists without key are matched by their index", () => {
  assert.deepEqual(diffConfigurations({l: [{a: 1}]}, {l: [{a: 2}, {a: 3}]}).map((change) => change.path), ["l[0].a", "l[1]"]);
});

test("changes are grouped by section and by element", () => {
  const changes = [...diffConfigurations(BEFORE, after()), ...diffConfigurations({project_name: "a"}, {project_name: "b"})];
  const nodeOf = (node) => ({
    label: node.label,
    kind: node.kind,
    count: changeCount(node),
    change: node.change?.type ?? null,
    rows: node.rows.map((row) => row.key + ":" + row.change.type),
    children: [...node.children.values()].map(nodeOf),
  });
  const tree = changeTree(changes);

  // the organization and its settings first, then the other sections in the order of the configuration
  assert.deepEqual(tree.map(([section]) => section), ["", "settings", "webhooks", "repositories"]);
  assert.deepEqual(nodeOf(tree[0][1]).rows, ["project_name:changed"]);
  assert.deepEqual(nodeOf(tree[1][1]).rows, ["web_commit_signoff_required:changed"]);
  assert.deepEqual(nodeOf(tree[3][1]), {
    label: "repositories",
    kind: "",
    count: 7,
    change: null,
    rows: [],
    children: [
      {
        label: "a",
        kind: "",
        count: 5,
        change: null,
        rows: ["has_wiki:changed", "topics:added", "topics:removed"],
        children: [
          {label: "main", kind: "rulesets", count: 1, change: "added", rows: [], children: []},
          {label: "main", kind: "branch_protection_rules", count: 1, change: null, rows: ["required_approving_review_count:changed"], children: []},
        ],
      },
      {label: "c", kind: "", count: 1, change: "added", rows: [], children: []},
      {label: "b", kind: "", count: 1, change: "removed", rows: [], children: []},
    ],
  });
});

test("the pattern of a change stands for all the elements of the lists", () => {
  const [change] = diffConfigurations(
    {repositories: [{name: "a", topics: ["x"], rulesets: [{name: "main", enforcement: "active"}]}]},
    {repositories: [{name: "a", topics: ["x"], rulesets: [{name: "main", enforcement: "disabled"}]}]},
  );

  assert.equal(change.path, "repositories[a].rulesets[main].enforcement");
  assert.equal(patternOf(change.segments), "repositories[*].rulesets[*].enforcement");
  assert.equal(patternOf(diffConfigurations({topics: ["x"]}, {topics: ["x", "y"]})[0].segments), "topics[]");
});
