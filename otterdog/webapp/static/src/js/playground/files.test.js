import assert from "node:assert/strict";
import {test} from "node:test";

import {fileResolver, fileRoles} from "./files.js";

// File-menu tests describe the loaded libraries and their imports. Error-link
// tests need only editor filenames and the filename reported by the evaluator.
// Browser tests in test_documents.py check the actual links and error marks.

test("the file menu shows which files import each library", () => {
  /**
   * The playground uses otterdog-defaults.libsonnet, which imports its sibling
   * otterdog-functions.libsonnet. The menu should show that relationship.
   * unused.libsonnet only imports itself, so it has no external importer to show.
   */
  const files = [
    {filename: "vendor/defaults/otterdog-defaults.libsonnet", content: "local functions = import 'otterdog-functions.libsonnet';"},
    {filename: "vendor/defaults/otterdog-functions.libsonnet", content: "{ name:: 'functions' }"},
    {filename: "vendor/defaults/unused.libsonnet", content: "local self_import = import 'unused.libsonnet';"},
  ];

  const roles = fileRoles(files, files[0].filename);

  assert.deepEqual(Object.fromEntries(roles), {
    "vendor/defaults/otterdog-defaults.libsonnet": ["the playground"],
    "vendor/defaults/otterdog-functions.libsonnet": ["otterdog-defaults.libsonnet"],
  });
});

test("the file menu lists both imported helpers when custom and upstream libraries share a name", () => {
  /**
   * A custom template imports its own helper with 'helper.libsonnet' and the
   * upstream helper with 'vendor/upstream/helper.libsonnet'. Both helpers have
   * the same basename, but both are used. Each helper's menu entry should say
   * 'imported by defaults.libsonnet', rather than assigning both imports to one.
   */
  const files = [
    {filename: "vendor/upstream/helper.libsonnet", content: "{}"},
    {filename: "vendor/custom/helper.libsonnet", content: "{}"},
    {
      filename: "vendor/custom/defaults.libsonnet",
      content: `local customHelper = import 'helper.libsonnet';
local upstreamHelper = import 'vendor/upstream/helper.libsonnet';
{}`,
    },
  ];

  const roles = fileRoles(files, "vendor/custom/defaults.libsonnet");

  assert.deepEqual(Object.fromEntries(roles), {
    "vendor/custom/defaults.libsonnet": ["the playground"],
    "vendor/custom/helper.libsonnet": ["defaults.libsonnet"],
    "vendor/upstream/helper.libsonnet": ["defaults.libsonnet"],
  });
});

test("an error with a full helper path opens that file even when library names match", () => {
  /**
   * Both libraries contain helper.libsonnet, but the error includes the full
   * path to the upstream helper. That path identifies exactly which editor to
   * open, regardless of the other helper's name.
   */
  const fileOf = fileResolver([
    "vendor/upstream/helper.libsonnet",
    "vendor/custom/helper.libsonnet",
  ]);

  const filename = fileOf({file: "vendor/upstream/helper.libsonnet"});

  assert.equal(filename, "vendor/upstream/helper.libsonnet");
});

test("an error with a unique helper name opens the matching library", () => {
  /**
   * The evaluator reports only helper.libsonnet. Only one loaded editor has
   * that filename, so the error link can safely open the custom helper.
   */
  const fileOf = fileResolver([
    "playground.jsonnet",
    "vendor/custom/helper.libsonnet",
  ]);

  const filename = fileOf({file: "helper.libsonnet"});

  assert.equal(filename, "vendor/custom/helper.libsonnet");
});

test("an error with a shared helper name stays unlinked", () => {
  /**
   * Both custom and upstream libraries contain helper.libsonnet. A function
   * called by the custom template might come from either helper. The reported
   * filename alone cannot identify its source, so neither editor is selected.
   */
  const fileOf = fileResolver([
    "vendor/custom/helper.libsonnet",
    "vendor/upstream/helper.libsonnet",
  ]);

  const filename = fileOf({file: "helper.libsonnet"});

  assert.equal(filename, undefined);
});

test("a parent-relative error path stays unlinked without a matching editor path", () => {
  /**
   * A nested library imports ../helper.libsonnet, and the evaluator reports that
   * relative spelling. The browser editor uses a full vendor path. Resolving
   * this spelling would require import context, which error links do not infer.
   */
  const fileOf = fileResolver(["vendor/custom/helper.libsonnet"]);

  const filename = fileOf({file: "../helper.libsonnet"});

  assert.equal(filename, undefined);
});
