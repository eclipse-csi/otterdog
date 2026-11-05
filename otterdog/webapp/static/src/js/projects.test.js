import assert from "node:assert/strict";
import {test} from "node:test";

import {countText, matches} from "./projects.js";

const CHE = {name: "ecd.che eclipse-che", group: "ecd", state: "configured", twoFactor: "true", permissions: "write"};
const PDE = {name: "eclipse.pde eclipse-pde", group: "eclipse", state: "unconfigured", twoFactor: "", permissions: ""};

test("without filters every organization is shown", () => {
  const filters = {q: "", group: "", state: "", settings: ""};

  assert.ok(matches(CHE, filters));
  assert.ok(matches(PDE, filters));
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

test("the settings to look at match the organizations whose configuration has them", () => {
  assert.ok(matches(CHE, {settings: "write"}));
  assert.ok(!matches(CHE, {settings: "two-factor"}));
  // without a configuration, nothing is known of its settings
  assert.ok(!matches(PDE, {settings: "write"}));
  assert.ok(!matches(PDE, {settings: "two-factor"}));
});

test("the count tells how many organizations are shown", () => {
  assert.equal(countText(120, 120), "120 organizations");
  assert.equal(countText(42, 120), "42 of 120 organizations");
  assert.equal(countText(1, 1), "1 organization");
});
