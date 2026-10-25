import assert from "node:assert/strict";
import fs from "node:fs";
import {test} from "node:test";

import {literalProperties} from "./jsonnet.js";
import {validate} from "./schema.js";
import {literalsOf} from "./validation.js";

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
