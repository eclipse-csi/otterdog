import assert from "node:assert/strict";
import fs from "node:fs";
import {test} from "node:test";

import {literalProperties} from "./jsonnet.js";
import {validate} from "./schema.js";
import {createsKind, literalsOf, otterdogDiagnostics} from "./validation.js";

// the schemas of otterdog, as passed to the playground
const SCHEMAS_DIR = new URL("../../../../../resources/schemas/", import.meta.url);
const SCHEMAS = Object.fromEntries(fs.readdirSync(SCHEMAS_DIR).map((name) => [name, JSON.parse(fs.readFileSync(new URL(name, SCHEMAS_DIR)))]));

const CODE = `local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';

orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('repo-a') {
      has_wiki: "yes",
      topics: ["a", 1],
      rulesets: [
        orgs.newRepoRuleset('main') {
          required_pull_request+: {
            required_approving_review_count: "0",
          },
        },
      ],
    },
    orgs.newRepo('repo-b') {
      has_wiki: "yes",
    },
  ],
}`;

// the evaluated value, only with the values the problems are about
const VALUE = {
  repositories: [
    {name: "repo-a", has_wiki: "yes", topics: ["a", 1], rulesets: [{name: "main", required_pull_request: {required_approving_review_count: "0"}}]},
    {name: "repo-b", has_wiki: "yes"},
  ],
};

// the problem of a value of an organization at a path
function problemAt(path, value) {
  const problem = validate(value, "organization.json", SCHEMAS).find((p) => JSON.stringify(p.path) === JSON.stringify(path));
  assert.ok(problem, "no problem at " + path.join("."));
  return problem;
}

const located = (path, value = VALUE, code = CODE) => literalsOf(problemAt(path, value), value, literalProperties(code))
  .map((literal) => code.slice(literal.from, literal.to));

test("problems are located at the literal values of the element they are about", () => {
  assert.deepEqual(located(["repositories", 0, "rulesets", 0, "required_pull_request", "required_approving_review_count"]), [
    "required_approving_review_count: \"0\"",
  ]);
  // the property of the repository with the same name
  const [literal] = literalsOf(problemAt(["repositories", 1, "has_wiki"], VALUE), VALUE, literalProperties(CODE));
  assert.equal(literal.from, CODE.lastIndexOf("has_wiki: \"yes\""));
  // a value of a list is located at the list
  assert.deepEqual(located(["repositories", 0, "topics", 1]), ["topics: [\"a\", 1]"]);
});

test("literal values that differ from the invalid value are not located", () => {
  const value = structuredClone(VALUE);
  value.repositories[1].has_wiki = 2;

  assert.deepEqual(located(["repositories", 1, "has_wiki"], value), []);
});

test("problems are not located at the same property of an object of another kind", () => {
  const code = `local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';

orgs.newOrg('my-project', 'my-org') {
  has_wiki: true,
  _repositories+:: [
    orgs.newRepo('repo-a') {
      has_wiki: true,
    },
  ],
}`;
  const value = {has_wiki: true, repositories: [{name: "repo-a", has_wiki: true}]};

  // the organization does not have this property of the repositories
  const [literal, ...others] = literalsOf(problemAt(["has_wiki"], value), value, literalProperties(code));
  assert.equal(literal.from, code.indexOf("has_wiki: true"));
  assert.deepEqual(others, []);
});

test("problems are located in the element containing them, e.g. the ruleset of a repository", () => {
  const code = `local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';

orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('a') {
      rulesets: [orgs.newRepoRuleset('main') { required_pull_request+: { required_approving_review_count: "0" } }],
    },
    orgs.newRepo('b') {
      rulesets: [orgs.newRepoRuleset('main') { required_pull_request+: { required_approving_review_count: "0" } }],
    },
  ],
}`;
  const ruleset = () => ({name: "main", required_pull_request: {required_approving_review_count: "0"}});
  const value = {repositories: [{name: "a", rulesets: [ruleset()]}, {name: "b", rulesets: [ruleset()]}]};
  const locatedIn = (repository) => {
    const problem = problemAt(["repositories", repository, "rulesets", 0, "required_pull_request", "required_approving_review_count"], value);
    return literalsOf(problem, value, literalProperties(code)).map((literal) => literal.from);
  };

  assert.deepEqual(locatedIn(0), [code.indexOf("required_approving_review_count")]);
  assert.deepEqual(locatedIn(1), [code.lastIndexOf("required_approving_review_count")]);
});

test("problems found by otterdog are located at the property they are about, otherwise at its repository or the organization", () => {
  const code = `local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';

orgs.newOrg('my-project', 'my-org') {
  settings+: {
    default_repository_permission: 'read',
  },
  _repositories+:: [
    orgs.newRepo('repo-a') {
      has_wiki: true,
      rulesets: [orgs.newRepoRuleset('main') { include_refs+: ['1.2.x'] }],
    },
    orgs.newRepo('repo-b') {
      has_wikki: true,
      rulesets: [orgs.newRepoRuleset('main') { include_refs+: ['~DEFAULT_BRANCH', '1.2.x'], target: 'branch', unknown: 1 }],
    },
  ],
}`;
  const problems = [
    // at the invalid value quoted after the property, in the ruleset of the repository
    {severity: "error", message: "repo_ruleset[name=\"main\", repository=repo-b] has an invalid 'include_refs' pattern '1.2.x', while only values ('refs/heads/*', '~DEFAULT_BRANCH', '~ALL') are allowed"},
    // a property of the organization
    {severity: "error", message: "settings has 'default_repository_permission' set to 'read' but 'none' is required."},
    // the property, whose value is not quoted
    {severity: "warning", message: "repository[name=\"repo-a\"] has 'has_wiki' enabled"},
    // a property not set in the code, e.g. inherited from the default configuration
    {severity: "warning", message: "repository[name=\"repo-a\"] has 'delete_branch_on_merge' disabled"},
    // the path of the object in the configuration rather than its header, e.g. for the unknown properties
    {severity: "warning", message: "repositories[name=\"repo-b\"] has the unknown property 'has_wikki', which otterdog ignores"},
    {severity: "warning", message: "repositories[name=\"repo-b\"].rulesets[name=\"main\"] has the unknown property 'unknown', which otterdog ignores"},
    {severity: "info", message: "use of organization roles requires an 'enterprise' plan"},
    {severity: "error", message: "repository[name=\"unknown\"] is not created by the code"},
  ];

  const located = otterdogDiagnostics(problems, code).map(({from, to, severity, source}) => [code.slice(from, to), severity, source]);
  assert.deepEqual(located, [
    ["'1.2.x'", "error", "otterdog"],
    ["'read'", "error", "otterdog"],
    ["has_wiki: true", "warning", "otterdog"],
    ["orgs.newRepo('repo-a')", "warning", "otterdog"],
    ["has_wikki: true", "warning", "otterdog"],
    ["unknown: 1", "warning", "otterdog"],
    ["orgs.newOrg", "info", "otterdog"],
    ["orgs.newOrg", "error", "otterdog"],
  ]);
  // the invalid value of the repository the problem is about
  const [ruleset] = otterdogDiagnostics(problems.slice(0, 1), code);
  assert.equal(ruleset.from, code.lastIndexOf("'1.2.x'"));
});

test("problems found by otterdog are only located at the objects of their kind", () => {
  const code = `local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';

orgs.newOrg('my-project', 'my-org') {
  teams+: [orgs.newTeam('shared') { description: 'team' }],
  _repositories+:: [
    orgs.newRepo('shared') { description: 'repository' },
  ],
}`;
  const problems = [
    {severity: "error", message: "repository[name=\"shared\"] has 'description' longer than 350 characters"},
    {severity: "warning", message: "teams[name=\"shared\"] has the unknown property 'description', which otterdog ignores"},
  ];

  const located = otterdogDiagnostics(problems, code).map(({from, to}) => code.slice(from, to));
  assert.deepEqual(located, ["description: 'repository'", "description: 'team'"]);
});

test("the functions creating the objects of a kind are recognized", () => {
  const creating = (kind) => ["newOrg", "newRepo", "extendRepo", "newBinaryRepo", "newRepoRuleset", "newOrgRuleset", "newTeam",
    "newRepoSecret", "newRepoDependabotSecret", "newBranchProtectionRule", "newCustomProperty"].filter((name) => createsKind(name, kind));

  assert.deepEqual(creating("repository"), ["newRepo", "extendRepo", "newBinaryRepo"]);
  assert.deepEqual(creating("repositories"), ["newRepo", "extendRepo", "newBinaryRepo"]);
  assert.deepEqual(creating("repo_ruleset"), ["newRepoRuleset"]);
  assert.deepEqual(creating("rulesets"), ["newRepoRuleset", "newOrgRuleset"]);
  assert.deepEqual(creating("repo_secret"), ["newRepoSecret"]);
  assert.deepEqual(creating("branch_protection_rules"), ["newBranchProtectionRule"]);
  assert.deepEqual(creating("custom_properties"), ["newCustomProperty"]);
  assert.deepEqual(creating("team"), ["newTeam"]);
});

test("problems found by otterdog are located at the nested property they are about, in their object", () => {
  const code = `local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';

orgs.newOrg('demo', 'demo-org') {
  _repositories+:: [
    orgs.newRepo('demo') {
      rulesets: [
        orgs.newRepoRuleset('main') {
          include_refs+: ['1.2.x'],
          required_pull_request+: { required_approving_review_count: 11 },
        },
      ],
    },
    orgs.newRepo('api') {
      rulesets: [
        orgs.newRepoRuleset('main') {
          include_refs+: ['1.2.x'],
          required_pull_request+: { required_approving_review_count: 11 },
        },
      ],
    },
  ],
}`;
  const problems = [
    // a property of an object nested in the ruleset, by its path
    {severity: "error", message: "repo_ruleset[name=\"main\", repository=demo] has 'required_pull_request.required_approving_review_count' of value '11' while only integers in the range [0, 10] are allowed."},
    // in the repository named like the organization, not in the other one
    {severity: "error", message: "repo_ruleset[name=\"main\", repository=demo] has an invalid 'include_refs' pattern '1.2.x'"},
  ];

  const [count, refs] = otterdogDiagnostics(problems, code);
  const repository = code.indexOf("orgs.newRepo('api')");
  assert.equal(code.slice(count.from, count.to), "11");
  assert.ok(count.from < repository);
  assert.equal(code.slice(refs.from, refs.to), "'1.2.x'");
  assert.ok(refs.from < repository);
  assert.equal(otterdogDiagnostics(problems, code).length, 2);
});

test("the objects of the headers of otterdog are read whatever the dots of their names", () => {
  const code = `local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';

orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('.github') {
      rulesets: [orgs.newRepoRuleset('main') { include_refs+: ['1.2.x'], foo: 1 }],
    },
  ],
}`;
  const problems = [
    {severity: "error", message: "repo_ruleset[name=\"main\", repository=.github] has an invalid 'include_refs' pattern '1.2.x'"},
    {severity: "warning", message: "repositories[name=\".github\"].rulesets[name=\"main\"] has the unknown property 'foo', which otterdog ignores"},
    // a long message without object, read in a time linear in its length
    {severity: "info", message: "a".repeat(100000) + " has 'foo'"},
  ];

  const located = otterdogDiagnostics(problems, code).map(({from, to}) => code.slice(from, to));
  assert.deepEqual(located, ["'1.2.x'", "foo: 1", "orgs.newOrg"]);
});
