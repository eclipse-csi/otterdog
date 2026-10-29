import assert from "node:assert/strict";
import {test} from "node:test";

import {fileResolver, fileRoles} from "./files.js";

// These tests exercise filename selection without a browser or a Jsonnet runtime.
// `files` describes the libraries the playground has loaded. Error locations are
// small stand-ins for parsed stack entries: only the reported filename matters
// here. Browser tests in test_documents.py check the actual links and error marks.

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

test("an error with only a shared helper name stays unlinked when its caller is unknown", () => {
  /**
   * Both the custom template and its upstream library contain helper.libsonnet.
   * The error names only 'helper.libsonnet', with no caller to tell them apart.
   * The playground must leave the source location unlinked rather than send
   * the user to whichever helper happens to appear first in the file list.
   */
  const files = [
    {filename: "vendor/upstream/helper.libsonnet", content: "{}"},
    {filename: "vendor/custom/helper.libsonnet", content: "{}"},
  ];
  const fileOf = fileResolver(files, files.map((file) => file.filename));
  const location = {file: "helper.libsonnet"};

  const filename = fileOf(location);

  assert.equal(filename, undefined);
});

test("a helper error links to the custom file when the caller imports its sibling helper", () => {
  /**
   * The error names 'helper.libsonnet'. Its next stack entry names the custom
   * defaults file, whose import 'helper.libsonnet' selects its sibling helper.
   * The error link must open vendor/custom/helper.libsonnet, even though an
   * upstream helper with the same name appears first in the file list.
   */
  const files = [
    {filename: "vendor/upstream/helper.libsonnet", content: "{}"},
    {filename: "vendor/custom/helper.libsonnet", content: "{}"},
    {filename: "vendor/custom/defaults.libsonnet", content: "local helper = import 'helper.libsonnet'; {}"},
  ];
  const fileOf = fileResolver(files, files.map((file) => file.filename));
  const location = {file: "helper.libsonnet"};
  const locations = [location, {file: "vendor/custom/defaults.libsonnet"}];

  const filename = fileOf(location, locations);

  assert.equal(filename, "vendor/custom/helper.libsonnet");
});

test("an unrelated caller cannot choose between helpers with the same name", () => {
  /**
   * The error names 'helper.libsonnet', which exists in two libraries. The next
   * known stack entry names a file that imports neither helper. Knowing that
   * file's name does not identify the failing helper, so the error stays unlinked.
   */
  const files = [
    {filename: "vendor/upstream/helper.libsonnet", content: "{}"},
    {filename: "vendor/custom/helper.libsonnet", content: "{}"},
    {filename: "vendor/other/defaults.libsonnet", content: "{}"},
  ];
  const fileOf = fileResolver(files, files.map((file) => file.filename));
  const location = {file: "helper.libsonnet"};
  const locations = [location, {file: "vendor/other/defaults.libsonnet"}];

  const filename = fileOf(location, locations);

  assert.equal(filename, undefined);
});

test("an error with a full helper path opens that file without needing a caller", () => {
  /**
   * Both libraries contain helper.libsonnet, but this error includes the full
   * path 'vendor/upstream/helper.libsonnet'. The path already identifies the
   * upstream editor, so the user can follow the source link without a caller.
   */
  const files = [
    {filename: "vendor/upstream/helper.libsonnet", content: "{}"},
    {filename: "vendor/custom/helper.libsonnet", content: "{}"},
  ];
  const fileOf = fileResolver(files, files.map((file) => file.filename));
  const location = {file: "vendor/upstream/helper.libsonnet"};

  const filename = fileOf(location);

  assert.equal(filename, "vendor/upstream/helper.libsonnet");
});
