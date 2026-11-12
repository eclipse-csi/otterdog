import assert from "node:assert/strict";
import {test} from "node:test";

import {formatDuration, parseDateTime, shortDateTime, statusColor, statusText, taskDuration} from "./datagrid.js";

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

test("a date and time of the api is read in UTC", () => {
  assert.equal(parseDateTime("2026-11-12T08:19:54.806000"), Date.UTC(2026, 10, 12, 8, 19, 54, 806));
  assert.equal(parseDateTime("2026-11-12T08:19:54"), Date.UTC(2026, 10, 12, 8, 19, 54));
  assert.equal(parseDateTime("2026-11-12T08:19:54.806Z"), Date.UTC(2026, 10, 12, 8, 19, 54, 806));
  assert.equal(parseDateTime("2026-11-12T09:19:54+01:00"), Date.UTC(2026, 10, 12, 8, 19, 54));
  assert.ok(Number.isNaN(parseDateTime("not a date")));
});

test("a duration is shown in the largest units", () => {
  assert.equal(formatDuration(0), "0.0s");
  assert.equal(formatDuration(1234), "1.2s");
  assert.equal(formatDuration(44_200), "44.2s");
  assert.equal(formatDuration(59_960), "1m 00s");
  assert.equal(formatDuration(389_000), "6m 29s");
  assert.equal(formatDuration(3_720_000), "1h 02m");
  assert.equal(formatDuration(-1), "");
  assert.equal(formatDuration(Number.NaN), "");
});

test("the duration of a task is known once it is finished or failed", () => {
  const task = {created_at: "2026-11-12T08:19:54.806000", updated_at: "2026-11-12T08:26:23.805000"};

  assert.equal(taskDuration({...task, status: "finished"}), "6m 29s");
  assert.equal(taskDuration({...task, status: "FAILED"}), "6m 29s");
  assert.equal(taskDuration({...task, status: "scheduled"}), "");
  assert.equal(taskDuration({...task, status: "created"}), "");
  assert.equal(taskDuration({status: "finished", created_at: "2026-11-12T08:19:54", updated_at: null}), "");
});
