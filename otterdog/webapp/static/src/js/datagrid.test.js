import assert from "node:assert/strict";
import {test} from "node:test";

import {shortDateTime, statusColor, statusText} from "./datagrid.js";

test("a date and time of the api is shown to the minute", () => {
  assert.equal(shortDateTime("2026-11-04T15:48:04.123000"), "2026-11-04 15:48");
  assert.equal(shortDateTime("2026-11-04T15:48:04"), "2026-11-04 15:48");
});

test("a status takes the color of its meaning", () => {
  assert.equal(statusColor("merged"), "success");
  assert.equal(statusColor("FINISHED"), "success");
  assert.equal(statusColor("failed"), "danger");
  assert.equal(statusColor("partially_applied"), "warning");
  assert.equal(statusColor("open"), "primary");
  assert.equal(statusColor("not_applied"), "secondary");
  assert.equal(statusColor("an unknown status"), "secondary");
});

test("the words of a status are separated by spaces", () => {
  assert.equal(statusText("not_applied"), "NOT APPLIED");
  assert.equal(statusText("open"), "OPEN");
});
