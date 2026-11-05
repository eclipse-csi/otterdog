import assert from "node:assert/strict";
import {test} from "node:test";

import {compare, countText, matches} from "./projects.js";

// the datasets of cards (includes/project-card.html)
const CHE = {name: "ecd.che eclipse-che", group: "ecd", repositories: "23", security: "70.0", pullRequests: "2"};
const PDE = {name: "eclipse.pde eclipse-pde", group: "eclipse", repositories: "-1", security: "-1", pullRequests: "0"};
const CSI = {name: "technology.csi eclipse-csi", group: "technology", repositories: "17", security: "95.0", pullRequests: "0"};

test("without filters every organization is shown", () => {
  const filters = {q: "", group: "", sort: ""};

  assert.ok([CHE, PDE, CSI].every((organization) => matches(organization, filters)));
});

test("the search matches the project or the organization, whatever its case", () => {
  assert.ok(matches(CHE, {q: "ECD.CHE"}));
  assert.ok(matches(CHE, {q: " eclipse-che "}));
  assert.ok(!matches(PDE, {q: "che"}));
});

test("an organization matches its top-level project", () => {
  assert.ok(matches(CHE, {group: "ecd"}));
  assert.ok(matches(CHE, {q: "che", group: "ecd"}));
  assert.ok(!matches(CHE, {group: "eclipse"}));
});

test("the organizations are sorted by name unless another order is chosen", () => {
  const sorted = (sort) => [CSI, PDE, CHE].sort(compare(sort)).map((organization) => organization.group);

  assert.deepEqual(sorted(""), ["ecd", "eclipse", "technology"]);
  assert.deepEqual(sorted("repositories"), ["ecd", "technology", "eclipse"]);
  assert.deepEqual(sorted("pull-requests"), ["ecd", "eclipse", "technology"]);
  // the least protected first, the organizations without statistics last
  assert.deepEqual(sorted("security"), ["ecd", "technology", "eclipse"]);
});

test("the count tells how many organizations are shown", () => {
  assert.equal(countText(120, 120), "120 organizations");
  assert.equal(countText(42, 120), "42 of 120 organizations");
  assert.equal(countText(1, 1), "1 organization");
});
