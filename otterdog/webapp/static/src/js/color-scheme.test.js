import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";

import {STORAGE_KEY, currentScheme, nextScheme} from "./color-scheme.js";

test("the mode set before the page renders is read from the same storage key", () => {
  const template = readFileSync(new URL("../../../templates/includes/color-scheme.html", import.meta.url), "utf8");

  assert.ok(template.includes(`localStorage.getItem("${STORAGE_KEY}")`));
});

test("a page without a dark mode is light", () => {
  assert.equal(currentScheme({dataset: {}}), "light");
  assert.equal(currentScheme({dataset: {bsTheme: "light"}}), "light");
  assert.equal(currentScheme({dataset: {bsTheme: "dark"}}), "dark");
});

test("the toggle switches to the other mode", () => {
  assert.equal(nextScheme("light"), "dark");
  assert.equal(nextScheme("dark"), "light");
});
