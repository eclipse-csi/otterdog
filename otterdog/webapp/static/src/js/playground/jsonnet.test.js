import assert from "node:assert/strict";
import {test} from "node:test";

import {completionContext, explicitValues, literalProperties, literalValue, mainCall, tokenize, topLevelLocals} from "./jsonnet.js";

const SNIPPET = `local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';
local wiki = true;

orgs.newOrg('my-project', 'my-org') {
  settings+: {
    web_commit_signoff_required: true, // a comment with { a brace
    description: "my { org",
  },
  _repositories+:: [
    orgs.newRepo('my-repo') {
      has_wiki: wiki,
      allow_merge_commit: true,
      topics+: ["a"],
      workflows+: {
        enabled: true,
      },
      rulesets: [
        orgs.newRepoRuleset('main') {
          required_pull_request+: {
            required_approving_review_count: 2,
          },
          required_status_checks: null,
        },
      ],
    },
  ],
}
`;

test("strings and comments do not contain tokens", () => {
  const tokens = tokenize("x: 'a { b', # c }\ny: |||\n  d }\n|||, // e }\nz: /* { */ 1");
  assert.deepEqual(tokens.map((token) => token.text), ["x", ":", "'a { b'", ",", "y", ":", "|||\n  d }\n|||", ",", "z", ":", "1"]);
});

test("literal values of the objects created by the default configuration are found", () => {
  const values = explicitValues(SNIPPET);

  assert.deepEqual(values.map(({call, path, value}) => [call, path.join("."), value]), [
    ["orgs.newOrg('my-project', 'my-org')", "settings.web_commit_signoff_required", "true"],
    ["orgs.newOrg('my-project', 'my-org')", "settings.description", "\"my { org\""],
    ["orgs.newRepo('my-repo')", "allow_merge_commit", "true"],
    ["orgs.newRepo('my-repo')", "workflows.enabled", "true"],
    ["orgs.newRepoRuleset('main')", "required_pull_request.required_approving_review_count", "2"],
    ["orgs.newRepoRuleset('main')", "required_status_checks", "null"],
  ]);
  // the range of a value is the one of its property, from its name to its value
  assert.equal(SNIPPET.slice(values[2].from, values[2].to), "allow_merge_commit: true");
});

test("values computed from other values are not compared", () => {
  const values = explicitValues("orgs.newRepo(name) { has_wiki: true }\norgs.newRepo('a') { has_wiki: wiki, x: std.length([]) }");

  assert.deepEqual(values, []);
});

test("completions are proposed for the functions and the properties of the default configuration", () => {
  const at = (marker) => {
    const offset = SNIPPET.indexOf(marker) + marker.length;
    return completionContext(SNIPPET, offset);
  };

  assert.deepEqual(at("orgs.newR"), {kind: "function", alias: "orgs", word: "newR", from: SNIPPET.indexOf("orgs.newR") + 5});
  assert.deepEqual(at("      allow_merge"), {
    kind: "property",
    scope: {function: "newRepo", call: "orgs.newRepo('my-repo')", exact: true, firstArgument: "my-repo", path: []},
    word: "allow_merge",
    from: SNIPPET.indexOf("allow_merge_commit"),
  });
  assert.deepEqual(at("        enabled").scope, {function: "newRepo", call: "orgs.newRepo('my-repo')", exact: true, firstArgument: "my-repo", path: ["workflows"]});
  // not in the value of a property, nor after an object that is not defined by the configuration, e.g. std
  assert.equal(at("allow_merge_commit: tr"), null);
  assert.equal(completionContext("local x = {};\nstd.l", 19), null);
});

test("the local definitions of the configuration are used, e.g. an extension of the default configuration", () => {
  const code = `local orgsOrig = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';
// a comment
local newBinaryRepo(name) =
  local prefix = "binaries";
  local repoName = name + "-" + prefix;
  orgsOrig.newRepo(repoName) { has_wiki: false };
local orgs = orgsOrig + { newRepo(name):: newBinaryRepo(name) }, unused = 1;

orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') { has_wiki: true },
  ],
}`;
  const locals = topLevelLocals(code);

  assert.deepEqual(locals.names, ["orgsOrig", "newBinaryRepo", "orgs", "unused"]);
  assert.ok(locals.text.endsWith("unused = 1;"));
  assert.equal(completionContext(code + "\norgs.newR", code.length + 10).kind, "function");
});

test("objects of functions of the configuration and extended objects are completed like the objects they return", () => {
  const code = `local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';
local newRuleset(name, checks) = orgs.newRepoRuleset(name) {
  allows_
};

orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.extendRepo('.github') {
      has_
    },
    orgs.newRepo('my-repo', org=$) {
      has_
    },
  ],
}`;
  const scopeAt = (marker, occurrence = 0) => {
    let offset = -1;
    for (let index = 0; index <= occurrence; index++) {
      offset = code.indexOf(marker, offset + 1);
    }
    return completionContext(code, offset + marker.length).scope;
  };

  assert.deepEqual(scopeAt("allows_"), {function: "newRepoRuleset", call: "orgs.newRepoRuleset('playground')", exact: false, firstArgument: undefined, path: []});
  assert.deepEqual(scopeAt("has_"), {function: "extendRepo", call: "orgs.newRepo('.github')", exact: false, firstArgument: ".github", path: []});
  assert.deepEqual(scopeAt("has_", 1), {function: "newRepo", call: "orgs.newRepo('my-repo')", exact: false, firstArgument: "my-repo", path: []});
  // only the values of exact calls are compared with the default configuration
  assert.deepEqual(explicitValues(code.replace("allows_", "allows_updates: true,")), []);
});

test("the literal properties of all the objects of the configuration are found, for the validation", () => {
  const code = SNIPPET.replace("allow_merge_commit: true", "allow_merge_commit: 'yes'").replace("orgs.newRepo('my-repo')", "orgs.extendRepo('my-repo')");
  const property = literalProperties(code).find((literal) => literal.path.join(".") === "allow_merge_commit");

  assert.deepEqual({...property, from: undefined, to: undefined}, {
    function: "extendRepo", call: "orgs.newRepo('my-repo')", exact: false, firstArgument: "my-repo", path: ["allow_merge_commit"],
    value: "'yes'", from: undefined, to: undefined, within: [{function: "newOrg", firstArgument: "my-project"}],
  });
  // the values of an object only extended are not compared with the default configuration
  assert.ok(!explicitValues(code).some((literal) => literal.path.join(".") === "allow_merge_commit"));
  // the calls creating the objects containing a ruleset
  const count = literalProperties(code).find((literal) => literal.path.at(-1) === "required_approving_review_count");
  assert.deepEqual(count.within, [{function: "extendRepo", firstArgument: "my-repo"}, {function: "newOrg", firstArgument: "my-project"}]);
});

test("the function called by the expression of the configuration is found", () => {
  const call = mainCall(SNIPPET);
  assert.equal(call.name, "newOrg");
  assert.equal(SNIPPET.slice(call.from, call.to), "orgs.newOrg");
  assert.equal(mainCall("local orgs = import 'x.libsonnet';\n// a repository\norgs.newRepo('my-repo') {}").name, "newRepo");
  assert.equal(mainCall("local orgs = import 'x.libsonnet';\nstd.length([])"), null);
  assert.equal(mainCall("{}"), null);
});

test("literal values are read as json", () => {
  assert.equal(literalValue("'0'"), "0");
  assert.equal(literalValue("'it\\'s \"quoted\"'"), "it's \"quoted\"");
  assert.equal(literalValue("2"), 2);
  assert.deepEqual(literalValue("[\"a\", null]"), ["a", null]);
  assert.equal(literalValue("{a: 1}"), undefined);
});
