import assert from "node:assert/strict";
import {test} from "node:test";

import {fileRoles} from "./files.js";

test("the files of the default configuration are listed with the files importing them", () => {
  const files = [
    {filename: "vendor/defaults/otterdog-defaults.libsonnet", content: "local functions = import 'otterdog-functions.libsonnet';"},
    {filename: "vendor/defaults/otterdog-functions.libsonnet", content: "{ name:: 'functions' }"},
    {filename: "vendor/defaults/unused.libsonnet", content: "local self_import = import 'unused.libsonnet';"},
  ];

  assert.deepEqual(Object.fromEntries(fileRoles(files, files[0].filename)), {
    "vendor/defaults/otterdog-defaults.libsonnet": ["the playground"],
    "vendor/defaults/otterdog-functions.libsonnet": ["otterdog-defaults.libsonnet"],
  });
});
