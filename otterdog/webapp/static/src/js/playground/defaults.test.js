import assert from "node:assert/strict";
import {test} from "node:test";

import {defaultsSnippet, explicitValues, tokenize} from "./defaults.js";

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

test("a snippet compares the values with the default configuration", () => {
  const values = explicitValues(SNIPPET);
  const snippet = defaultsSnippet(SNIPPET, values);

  assert.ok(snippet.startsWith("local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';\n"));
  assert.ok(snippet.includes("  defaultsSame(orgs.newRepo('my-repo'), [\"allow_merge_commit\"], true),"));
  assert.equal(defaultsSnippet("{}", []), null);
});
