import assert from "node:assert/strict";
import fs from "node:fs";
import {test} from "node:test";

import {formatPath, schemaOfFunction, validate} from "./schema.js";

// the schemas of otterdog, as passed to the playground
const SCHEMAS_DIR = new URL("../../../../../resources/schemas/", import.meta.url);
const SCHEMAS = Object.fromEntries(fs.readdirSync(SCHEMAS_DIR).map((name) => [name, JSON.parse(fs.readFileSync(new URL(name, SCHEMAS_DIR)))]));

const ORGANIZATION = {
  project_name: "my-project",
  github_id: "my-org",
  settings: {name: "My org", web_commit_signoff_required: true},
  repositories: [{
    name: "my-repo",
    description: null,
    private: false,
    has_wiki: true,
    topics: ["a"],
    rulesets: [{
      name: "main",
      enforcement: "active",
      required_pull_request: {required_approving_review_count: 1, allowed_merge_methods: ["merge"]},
    }],
  }],
};

const problemsOf = (change, schema = "organization.json") => {
  const value = structuredClone(ORGANIZATION);
  change(value);
  return validate(value, schema, SCHEMAS).map((problem) => [problem.severity, formatPath(value, problem.path), problem.message]);
};

test("a valid configuration has no problem", () => {
  assert.deepEqual(problemsOf(() => {}), []);
});

test("values of a wrong type are errors", () => {
  assert.deepEqual(problemsOf((org) => (org.repositories[0].rulesets[0].required_pull_request.required_approving_review_count = "0")), [
    ["error", "repositories[name=\"my-repo\"].rulesets[name=\"main\"].required_pull_request.required_approving_review_count", "\"0\" is not of type integer"],
  ]);
  assert.deepEqual(problemsOf((org) => (org.repositories[0].description = 3)), [
    ["error", "repositories[name=\"my-repo\"].description", "3 is not of type string or null"],
  ]);
  assert.deepEqual(problemsOf((org) => (org.repositories[0].topics = ["a", 1])), [["error", "repositories[name=\"my-repo\"].topics[1]", "1 is not of type string"]]);
});

test("unknown properties are warnings, unless they are not allowed", () => {
  assert.deepEqual(problemsOf((org) => (org.repositories[0].has_wikki = true)), [["warning", "repositories[name=\"my-repo\"].has_wikki", "unknown property"]]);
  assert.deepEqual(problemsOf((org) => (org.repositories[0].rulesets[0].unknown = true)), [
    ["error", "repositories[name=\"my-repo\"].rulesets[name=\"main\"].unknown", "unknown property"],
  ]);
  // an unknown property of an alternative of 'anyOf' makes the value invalid
  assert.deepEqual(problemsOf((org) => (org.repositories[0].rulesets[0].required_pull_request.unknown = true)), [
    ["error", "repositories[name=\"my-repo\"].rulesets[name=\"main\"].required_pull_request.unknown", "unknown property"],
  ]);
});

test("missing properties, values not allowed and duplicates are errors", () => {
  assert.deepEqual(problemsOf((org) => delete org.repositories[0].rulesets[0].enforcement), [
    ["error", "repositories[name=\"my-repo\"].rulesets[name=\"main\"]", "the required property \"enforcement\" is missing"],
  ]);
  assert.deepEqual(problemsOf((org) => (org.repositories[0].rulesets[0].required_pull_request.allowed_merge_methods = ["merge", "merge", "fast-forward"])), [
    ["error", "repositories[name=\"my-repo\"].rulesets[name=\"main\"].required_pull_request.allowed_merge_methods[2]", "\"fast-forward\" is not one of \"merge\", \"squash\", \"rebase\""],
    ["error", "repositories[name=\"my-repo\"].rulesets[name=\"main\"].required_pull_request.allowed_merge_methods", "contains duplicate elements"],
  ]);
});

test("the objects created by the functions of the default configuration are validated with their schema", () => {
  assert.equal(schemaOfFunction("newRepo"), "repository.json");
  assert.equal(schemaOfFunction("newPullRequest"), "ruleset.json#/$defs/pull_request");
  assert.equal(schemaOfFunction("newOrgDependabotSecret"), "org-secret.json");
  assert.equal(schemaOfFunction("newRepoCodespacesSecret"), "repo-secret.json");
  assert.equal(schemaOfFunction("unknown"), null);
  assert.deepEqual(validate({required_approving_review_count: "0"}, schemaOfFunction("newPullRequest"), SCHEMAS).map((problem) => problem.path), [["required_approving_review_count"]]);
});

test("values that otterdog does not allow are errors, e.g. an unknown code scanning language", () => {
  const [problem, ...others] = problemsOf((org) => (org.repositories[0].code_scanning_default_languages = ["python", "truc"]));

  assert.deepEqual(others, []);
  assert.deepEqual(problem.slice(0, 2), ["error", "repositories[name=\"my-repo\"].code_scanning_default_languages[1]"]);
  assert.match(problem[2], /^"truc" is not one of "actions", "c-cpp", .*"rust"/);
});
