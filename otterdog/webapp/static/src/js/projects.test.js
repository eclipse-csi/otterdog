import assert from "node:assert/strict";
import {test} from "node:test";

import {compare, countText, groupsToggle, matches} from "./projects.js";

// the datasets of cards (includes/project-card.html)
const CHE = {
  name: "ecd.che eclipse-che", group: "ecd", repositories: "23", security: "70.0", pullRequests: "2",
  branchProtection: "40.0", secretScanning: "100.0", dependabot: "60.0", codeScanning: "80.0",
  scorecard: "6.40", blueprints: "1", changed: "1762300000",
};
const PDE = {
  name: "eclipse.pde eclipse-pde", group: "eclipse", repositories: "-1", security: "-1", pullRequests: "0",
  branchProtection: "-1", secretScanning: "-1", dependabot: "-1", codeScanning: "-1",
  scorecard: "-1", blueprints: "0", changed: "-1",
};
const CSI = {
  name: "technology.csi eclipse-csi", group: "technology", repositories: "17", security: "95.0", pullRequests: "0",
  branchProtection: "90.0", secretScanning: "100.0", dependabot: "100.0", codeScanning: "90.0",
  scorecard: "7.50", blueprints: "3", changed: "1762000000",
};

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

test("the organizations are sorted by each protection, their score, their blueprints and their changes", () => {
  const sorted = (sort) => [CSI, PDE, CHE].sort(compare(sort)).map((organization) => organization.group);

  assert.deepEqual(sorted("branch-protection"), ["ecd", "technology", "eclipse"]);
  // a tie breaks by the name, the unknown values last
  assert.deepEqual(sorted("secret-scanning"), ["ecd", "technology", "eclipse"]);
  assert.deepEqual(sorted("dependabot"), ["ecd", "technology", "eclipse"]);
  assert.deepEqual(sorted("code-scanning"), ["ecd", "technology", "eclipse"]);
  assert.deepEqual(sorted("scorecard"), ["ecd", "technology", "eclipse"]);
  assert.deepEqual(sorted("blueprints"), ["technology", "ecd", "eclipse"]);
  assert.deepEqual(sorted("changed-recently"), ["ecd", "technology", "eclipse"]);
  assert.deepEqual(sorted("changed-long-ago"), ["technology", "ecd", "eclipse"]);
});

test("the count tells how many organizations are shown", () => {
  assert.equal(countText(120, 120), "120 organizations");
  assert.equal(countText(42, 120), "42 of 120 organizations");
  assert.equal(countText(1, 1), "1 organization");
});

test("the button of the groups folds them when one is open, else unfolds them", () => {
  assert.deepEqual(groupsToggle(true), {label: "Collapse all the groups", icon: "fa-angles-up"});
  assert.deepEqual(groupsToggle(false), {label: "Expand all the groups", icon: "fa-angles-down"});
});
