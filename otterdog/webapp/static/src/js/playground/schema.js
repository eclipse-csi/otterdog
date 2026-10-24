import {formatValue, isObject} from "./values.js";

// The validation of the evaluated configurations with the JSON schemas of otterdog (otterdog/resources/schemas), which
// otterdog validates configurations with before applying them. Only the keywords used by these schemas are supported.

// the schemas of the objects created by the functions of the default configuration
const FUNCTION_SCHEMAS = {
  newOrg: "organization.json",
  newCustomProperty: "custom-property.json",
  newOrgRole: "org-role.json",
  newTeam: "team.json",
  newOrgWebhook: "webhook.json",
  newOrgSecret: "org-secret.json",
  newOrgVariable: "org-variable.json",
  newOrgRuleset: "org-ruleset.json",
  newRepo: "repository.json",
  extendRepo: "repository.json",
  newRepoWebhook: "webhook.json",
  newRepoSecret: "repo-secret.json",
  newRepoVariable: "repo-variable.json",
  newBranchProtectionRule: "branch-protection-rule.json",
  newRepoRuleset: "repo-ruleset.json",
  newPullRequest: "ruleset.json#/$defs/pull_request",
  newStatusChecks: "ruleset.json#/$defs/status_check",
  newMergeQueue: "ruleset.json#/$defs/merge_queue",
  newEnvironment: "environment.json",
  newEnvSecret: "environment-secret.json",
  newEnvVariable: "environment-variable.json",
};

const TYPES = {
  array: Array.isArray,
  boolean: (value) => typeof value === "boolean",
  integer: Number.isInteger,
  null: (value) => value === null,
  number: (value) => typeof value === "number",
  object: isObject,
  string: (value) => typeof value === "string",
};

// the schema of the objects created by a function of the default configuration, e.g. 'repository.json' for newRepo
export const schemaOfFunction = (name) => FUNCTION_SCHEMAS[name] ?? null;

// Returns the problems of a value for a schema, e.g. 'repository.json', as {severity, path, message, refs}, path being
// the property names and the indexes leading to the invalid value, and refs the schemas {path, ref} that the values
// containing it were validated with, e.g. {path: ["repositories", 0], ref: "repository.json"}. Like otterdog, unknown properties are warnings, as
// otterdog ignores them, unless a schema forbids them, e.g. the settings of a ruleset, the other problems are errors.
export function validate(value, ref, schemas) {
  const problems = [];
  const {schema, file} = resolve(ref, null, schemas);
  check(value, schema, {file, schemas, path: [], problems, refs: [{path: [], ref}]});
  return problems;
}

// the path of a value as otterdog reports it, the elements of lists being named if possible, e.g.
// 'repositories[name="my-repo"].rulesets[name="main"].required_pull_request'
export function formatPath(value, path) {
  let result = "";
  for (const key of path) {
    value = value?.[key];
    if (typeof key === "number") {
      result += isObject(value) && "name" in value ? "[name=\"" + value.name + "\"]" : "[" + key + "]";
    } else {
      result += result === "" ? key : "." + key;
    }
  }
  return result;
}

// a schema referenced by a file and a pointer, e.g. 'types.json#/$defs/string-or-null', or '#/$defs/pull_request' in the
// file of the referencing schema
function resolve(ref, file, schemas) {
  const [name, pointer = ""] = ref.split("#");
  const target = name === "" ? file : name;
  const schema = pointer.split("/").filter((key) => key !== "").reduce((node, key) => node[key], schemas[target]);
  return {schema, file: target};
}

const report = (context, severity, message, path = context.path) => context.problems.push({severity, path, message, refs: context.refs});

// checks a value, returns the names of the properties the schema evaluated, for unevaluatedProperties
function check(value, schema, context) {
  const evaluated = new Set();
  if (schema.$ref !== undefined) {
    const target = resolve(schema.$ref, context.file, context.schemas);
    const ref = schema.$ref.startsWith("#") ? context.file + schema.$ref : schema.$ref;
    const refs = [...context.refs, {path: context.path, ref}];
    check(value, target.schema, {...context, file: target.file, refs}).forEach((key) => evaluated.add(key));
  }
  if (!hasType(value, schema.type)) {
    report(context, "error", formatValue(value) + " is not of type " + [schema.type].flat().join(" or "));
    return evaluated;
  }
  if (!isAllowed(value, schema.enum)) {
    report(context, "error", formatValue(value) + " is not one of " + schema.enum.map((option) => JSON.stringify(option)).join(", "));
  }
  if (schema.anyOf !== undefined) {
    checkAnyOf(value, schema.anyOf, context).forEach((key) => evaluated.add(key));
  }
  if (isObject(value)) {
    checkObject(value, schema, context, evaluated);
  } else if (Array.isArray(value)) {
    checkList(value, schema, context);
  }
  return evaluated;
}

const hasType = (value, type) => type === undefined || [type].flat().some((name) => TYPES[name](value));

const isAllowed = (value, options) => options === undefined || options.some((option) => JSON.stringify(option) === JSON.stringify(value));

// A value is valid if it is valid for one of the schemas. Otherwise, the problems reported are the ones of the schema
// of its type, e.g. the ones of a ruleset rather than that it is not null, all of them being errors.
function checkAnyOf(value, schemas, context) {
  const results = schemas.map((schema) => {
    const problems = [];
    return {evaluated: check(value, schema, {...context, problems}), problems};
  });
  const valid = results.filter((result) => result.problems.length === 0);
  if (valid.length > 0) {
    return new Set(valid.flatMap((result) => [...result.evaluated]));
  }

  const types = schemas.map((schema) => typesOf(schema, context.file, context.schemas));
  const matching = results.find((result, index) => types[index].some((type) => TYPES[type](value)));
  if (matching === undefined) {
    report(context, "error", formatValue(value) + " is not of type " + [...new Set(types.flat())].join(" or "));
  } else {
    matching.problems.forEach((problem) => context.problems.push({...problem, severity: "error"}));
  }
  return new Set();
}

// the types of the values of a schema, all of them if it does not restrict them
function typesOf(schema, file, schemas) {
  if (schema.type !== undefined) {
    return [schema.type].flat();
  }
  if (schema.$ref !== undefined) {
    const target = resolve(schema.$ref, file, schemas);
    return typesOf(target.schema, target.file, schemas);
  }
  return Object.keys(TYPES);
}

function checkObject(value, schema, context, evaluated) {
  for (const [key, property] of Object.entries(value)) {
    const schemas = propertySchemas(schema, key);
    schemas.forEach((propertySchema) => checkProperty(property, propertySchema, {...context, path: [...context.path, key]}));
    if (schemas.length > 0) {
      evaluated.add(key);
    }
  }

  for (const key of schema.required ?? []) {
    if (!Object.hasOwn(value, key)) {
      report(context, "error", "the required property \"" + key + "\" is missing");
    }
  }
  if (schema.unevaluatedProperties === false) {
    Object.keys(value).filter((key) => !evaluated.has(key))
      .forEach((key) => report(context, "error", "unknown property", [...context.path, key]));
  }
}

// the schemas of a property: the ones of its name and of the patterns it matches, otherwise the one of the other
// properties if any, e.g. false if they are not allowed
function propertySchemas(schema, key) {
  const schemas = [
    schema.properties?.[key],
    ...Object.entries(schema.patternProperties ?? {}).filter(([pattern]) => new RegExp(pattern, "u").test(key)).map(([, s]) => s),
  ].filter((propertySchema) => propertySchema !== undefined);
  return schemas.length > 0 || schema.additionalProperties === undefined ? schemas : [schema.additionalProperties];
}

// a property forbidden by additionalProperties is only ignored by otterdog
function checkProperty(value, schema, context) {
  if (schema === false) {
    report(context, "warning", "unknown property");
  } else {
    check(value, schema, context);
  }
}

function checkList(value, schema, context) {
  if (schema.items !== undefined) {
    value.forEach((item, index) => check(item, schema.items, {...context, path: [...context.path, index]}));
  }
  if (schema.minItems !== undefined && value.length < schema.minItems) {
    report(context, "error", "expected at least " + schema.minItems + " element(s)");
  }
  if (schema.uniqueItems && new Set(value.map((item) => JSON.stringify(item))).size < value.length) {
    report(context, "error", "contains duplicate elements");
  }
}
