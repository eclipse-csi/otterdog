import assert from "node:assert/strict";
import {test} from "node:test";

import {compare, countText, matches} from "./projects.js";

// the datasets of cards (includes/project-card.html)
const CHE = {
  name: "ecd.che eclipse-che", group: "ecd", state: "configured", attention: "write pull-requests",
  repositories: "23", security: "70.0", pullRequests: "2",
};
const PDE = {
  name: "eclipse.pde eclipse-pde", group: "eclipse", state: "unconfigured", attention: "unconfigured",
  repositories: "-1", security: "-1", pullRequests: "0",
};
const CSI = {
  name: "technology.csi eclipse-csi", group: "technology", state: "configured", attention: "",
  repositories: "17", security: "95.0", pullRequests: "0",
};

test("without filters every organization is shown", () => {
  const filters = {q: "", group: "", state: "", attention: "", sort: ""};

  assert.ok([CHE, PDE, CSI].every((organization) => matches(organization, filters)));
});

test("the search matches the project or the organization, whatever its case", () => {
  assert.ok(matches(CHE, {q: "ECD.CHE"}));
  assert.ok(matches(CHE, {q: " eclipse-che "}));
  assert.ok(!matches(PDE, {q: "che"}));
});

test("an organization matches its top-level project and its state", () => {
  assert.ok(matches(CHE, {group: "ecd", state: "configured"}));
  assert.ok(!matches(CHE, {group: "eclipse"}));
  assert.ok(!matches(CHE, {state: "unconfigured"}));
});

test("the organizations to look at match any of their reasons or a given one", () => {
  assert.ok(matches(CHE, {attention: "any"}));
  assert.ok(matches(PDE, {attention: "any"}));
  assert.ok(!matches(CSI, {attention: "any"}));
  assert.ok(matches(CHE, {attention: "write"}));
  assert.ok(!matches(CHE, {attention: "two-factor"}));
  // a reason is a whole word: write does not match a hypothetical rewrite
  assert.ok(!matches({...CSI, attention: "rewrite"}, {attention: "write"}));
});

test("the organizations are sorted by name unless another order is chosen", () => {
  const sorted = (sort) => [CSI, PDE, CHE].sort(compare(sort)).map((organization) => organization.group);

  assert.deepEqual(sorted(""), ["ecd", "eclipse", "technology"]);
  assert.deepEqual(sorted("attention"), ["ecd", "eclipse", "technology"]);
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
