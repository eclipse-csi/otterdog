import assert from "node:assert/strict";
import {test} from "node:test";

import {fileResolver, fileRoles} from "./files.js";

// These tests exercise filename selection without a browser or a Jsonnet runtime.
// `files` describes the libraries the playground has loaded. Error locations are
// small stand-ins for parsed stack entries: only the reported filename matters
// here. Browser tests in test_documents.py check the actual links and error marks.

/**
 * Resolve an error's reported filename using the loaded libraries and callers.
 * Build only the filename fields of a parsed error stack: the failure comes
 * first, followed by the callers in the order the evaluator reports them.
 * The tests keep the library contents and caller paths explicit; line and
 * column positions do not affect which editor the error link should open.
 */
function resolveErrorFile({files, reportedFile, callers = []}) {
  const fileOf = fileResolver(files, files.map((file) => file.filename));
  const location = {file: reportedFile};
  const locations = [location, ...callers.map((file) => ({file}))];
  return fileOf(location, locations);
}

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

  const filename = resolveErrorFile({files, reportedFile: "helper.libsonnet"});

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

  const filename = resolveErrorFile({
    files,
    reportedFile: "helper.libsonnet",
    callers: ["vendor/custom/defaults.libsonnet"],
  });

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

  const filename = resolveErrorFile({
    files,
    reportedFile: "helper.libsonnet",
    callers: ["vendor/other/defaults.libsonnet"],
  });

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

  const filename = resolveErrorFile({files, reportedFile: "vendor/upstream/helper.libsonnet"});

  assert.equal(filename, "vendor/upstream/helper.libsonnet");
});


test("a shortened upstream caller links a helper error to the upstream library", () => {
  /**
   * Both custom and upstream defaults import their own helper.libsonnet. The
   * stack names the upstream defaults as 'upstream/defaults.libsonnet', then
   * the custom defaults by its full path. That shortened upstream path uniquely
   * identifies its file. Use its sibling helper, not the custom caller's helper.
   */
  const files = [
    {filename: "vendor/custom/helper.libsonnet", content: "{}"},
    {filename: "vendor/custom/upstream/helper.libsonnet", content: "{}"},
    {filename: "vendor/custom/upstream/defaults.libsonnet", content: "local helper = import 'helper.libsonnet'; {}"},
    {
      filename: "vendor/custom/defaults.libsonnet",
      content: `local upstream = import 'upstream/defaults.libsonnet';
local helper = import 'helper.libsonnet';
{}`,
    },
  ];

  const filename = resolveErrorFile({
    files,
    reportedFile: "helper.libsonnet",
    callers: ["upstream/defaults.libsonnet", "vendor/custom/defaults.libsonnet"],
  });

  assert.equal(filename, "vendor/custom/upstream/helper.libsonnet");
});

test("an ambiguous caller leaves the helper error unlinked even when an outer caller is known", () => {
  /**
   * Two loaded libraries contain upstream/defaults.libsonnet, each importing a
   * helper of its own. The shortened caller path cannot distinguish them.
   * A later custom caller also imports helper.libsonnet, but its import does not
   * identify which upstream helper failed. Leave the error unlinked.
   */
  const files = [
    {filename: "vendor/custom/helper.libsonnet", content: "{}"},
    {filename: "vendor/first/upstream/helper.libsonnet", content: "{}"},
    {filename: "vendor/second/upstream/helper.libsonnet", content: "{}"},
    {filename: "vendor/first/upstream/defaults.libsonnet", content: "import 'helper.libsonnet'"},
    {filename: "vendor/second/upstream/defaults.libsonnet", content: "import 'helper.libsonnet'"},
    {filename: "vendor/custom/defaults.libsonnet", content: "import 'helper.libsonnet'"},
  ];

  const filename = resolveErrorFile({
    files,
    reportedFile: "helper.libsonnet",
    callers: ["upstream/defaults.libsonnet", "vendor/custom/defaults.libsonnet"],
  });

  assert.equal(filename, undefined);
});

test("an unavailable caller cannot be skipped to choose an outer caller's helper", () => {
  /**
   * The helper filename is ambiguous and the immediate caller is unavailable.
   * The known outer caller imports its own helper, but the missing file might
   * have imported the other helper. Do not turn that uncertainty into a link
   * to the outer caller's file.
   */
  const files = [
    {filename: "vendor/custom/helper.libsonnet", content: "{}"},
    {filename: "vendor/upstream/helper.libsonnet", content: "{}"},
    {filename: "vendor/custom/defaults.libsonnet", content: "import 'helper.libsonnet'"},
  ];

  const filename = resolveErrorFile({
    files,
    reportedFile: "helper.libsonnet",
    callers: ["unavailable.libsonnet", "vendor/custom/defaults.libsonnet"],
  });

  assert.equal(filename, undefined);
});
