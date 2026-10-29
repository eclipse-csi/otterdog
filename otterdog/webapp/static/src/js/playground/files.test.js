import assert from "node:assert/strict";
import {test} from "node:test";

import {fileResolver, fileRoles} from "./files.js";

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

test("relative custom imports and package imports have their own owners", () => {
  const files = [
    {filename: "otterdog/resources/defaults/helper.libsonnet", content: "{}"},
    {filename: "vendor/custom/helper.libsonnet", content: "{}"},
    {filename: "vendor/custom/defaults.libsonnet", content: "local a = import 'helper.libsonnet'; local b = import 'otterdog/resources/defaults/helper.libsonnet'; {}"},
  ];
  assert.deepEqual(Object.fromEntries(fileRoles(files, files[2].filename)), {
    "vendor/custom/defaults.libsonnet": ["the playground"],
    "vendor/custom/helper.libsonnet": ["defaults.libsonnet"],
    "otterdog/resources/defaults/helper.libsonnet": ["defaults.libsonnet"],
  });
});


test("ambiguous helper locations need an importing frame, and aliases retain their owner", () => {
  const files = [
    {filename: "otterdog/resources/defaults/helper.libsonnet", aliases: ["vendor/custom/otterdog/resources/defaults/helper.libsonnet"], content: "{}"},
    {filename: "vendor/custom/helper.libsonnet", content: "{}"},
    {filename: "vendor/custom/defaults.libsonnet", content: "local helper = import 'helper.libsonnet'; {}"},
    {filename: "vendor/other/defaults.libsonnet", content: "{}"},
  ];
  const fileOf = fileResolver(files, files.map((file) => file.filename));
  const location = {file: "helper.libsonnet"};
  assert.equal(fileOf(location), undefined, "no arbitrary first match without stack context");
  assert.equal(fileOf(location, [location, {file: files[2].filename}]), files[1].filename);
  assert.equal(fileOf(location, [location, {file: files[3].filename}]), undefined, "an unrelated frame is insufficient");
  assert.equal(fileOf({file: files[0].filename}), files[0].filename);
  assert.equal(fileOf({file: files[0].aliases[0]}), files[0].filename);
});
