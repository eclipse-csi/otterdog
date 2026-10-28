import {setDiagnostics} from "@codemirror/lint";

import {actionLink, element, icon} from "./dom.js";
import {literalProperties, literalValue, mainCall, propertiesOf, repositoryCall, tokenize} from "./jsonnet.js";
import {formatPath, schemaOfFunction, validate} from "./schema.js";
import {isObject} from "./values.js";

// The problems of the evaluated value of the shown document for the JSON schemas of otterdog, see schema.js, e.g. a
// string instead of a number, which otterdog rejects, or an unknown property, which otterdog ignores. The value is
// validated if the document calls a function of the default configuration, e.g. `orgs.newOrg(...)`. The problems are
// reported as diagnostics of the editor, at the literal values they are about, otherwise at this call.
//
// The configuration of an organization can also be validated by otterdog once asked to, see validateWithOtterdog: its
// value is posted to the server, which validates it like `otterdog validate`, without the validations depending on the
// current state of the organization on GitHub, e.g. an invalid pattern of the branches of a ruleset. These problems
// are shown with the ones of the schemas as long as the content of the document does not change.
//
// Returns the functions showing the problems of a document for its value, clearing them, telling why a document
// cannot be validated by otterdog, and validating it, with dispatch(d, spec) applying a transaction to a document.
// showNote is called with the document, the key of the note, 'problems' or 'validation', and the note telling the
// number of problems, null if none, which shows them with showProblems when clicked. The note of the validation by
// otterdog links its limitations in the documentation.
export function createValidation({schemas, validationUrl, documentationUrl, dispatch, showProblems, showNote}) {
  const limitationsUrl = documentationUrl + LIMITATIONS_PAGE;
  // the number of schema errors of the shown value of a document: {code, errors}
  const schemaErrors = new WeakMap();
  // the last validation by otterdog of a document: {code, pending}, {code, problems} or {code, error}
  const validations = new WeakMap();

  function show(d, value) {
    const code = d.code;
    const call = mainCall(code);
    const schema = call === null ? null : schemaOfFunction(call.name);
    const problems = schema === null ? [] : validate(value, schema, schemas);
    const literals = problems.length === 0 ? [] : literalProperties(code);

    const diagnostics = problems.flatMap((problem) => {
      const located = literalsOf(problem, value, literals);
      const message = describe(problem, value);
      return (located.length > 0 ? located : [call]).map(({from, to}) => ({from, to, severity: problem.severity, source: "schema", message}));
    });
    schemaErrors.set(d, {code, errors: problems.filter((problem) => problem.severity === "error").length});

    // the validation by otterdog of another content no longer applies
    const validated = validations.get(d)?.code === code ? validations.get(d) : null;
    const validatedDiagnostics = validated?.problems === undefined ? [] : otterdogDiagnostics(validated.problems, code);
    dispatch(d, setDiagnostics(d.state, [...diagnostics, ...validatedDiagnostics]));
    showNote(d, "problems", noteOf(problems, showProblems));
    showNote(d, "validation", validated === null ? null : validationNote(validated, showProblems, limitationsUrl));
  }

  function clear(d) {
    dispatch(d, setDiagnostics(d.state, []));
  }

  // the reason why the shown content of a document cannot be validated by otterdog, null if it can
  function reasonNotToValidate(d) {
    const code = d.code;
    if (!isOrganization(d)) {
      return "Only the configuration of an organization, created by `orgs.newOrg(...)`, can be validated by otterdog";
    }
    if (d.result?.code !== code || d.result.value === undefined) {
      return "The document is validated once it has been evaluated without error";
    }
    if (schemaErrors.get(d)?.code !== code || schemaErrors.get(d).errors > 0) {
      return "Otterdog does not validate a configuration with schema errors, fix them first";
    }
    if (validations.get(d)?.code === code && validations.get(d).pending) {
      return "The document is being validated";
    }
    return null;
  }

  // validates the shown value of a document with otterdog, and shows its problems if its content did not change
  async function validateWithOtterdog(d) {
    const {code, value} = d.result;
    const pending = {code, pending: true};
    validations.set(d, pending);
    showNote(d, "validation", validationNote(pending, showProblems, limitationsUrl));

    const validated = await validationOf(validationUrl, value);
    // a later validation of the document, e.g. of its changed content, replaces this one
    if (validations.get(d) !== pending) {
      return;
    }
    validations.set(d, {code, ...validated});
    if (d.code === code) {
      show(d, value);
    }
  }

  return {show, clear, isOrganization, reasonNotToValidate, validateWithOtterdog};
}

// whether a document is the configuration of an organization, the only one validated by otterdog
const isOrganization = (d) => mainCall(d.code)?.name === "newOrg";

// the limitations of the validation by otterdog, detailed in the documentation
export const VALIDATION_LIMITATIONS = "Not checked: the members of the teams being members of the organization, the"
  + " languages of code scanning being detected in the repositories, the teams, users and apps of bypass actors"
  + " existing, and whether the changes can be merged automatically. A pull request is still validated by otterdog.";
const LIMITATIONS_PAGE = "userguide/guides/troubleshooting/#validation-in-the-playground";

// the validation of an evaluated configuration by otterdog: {problems} or {error}
async function validationOf(url, value) {
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(value),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !Array.isArray(body.problems)) {
      return {error: body.error ?? "the server answered with the status " + response.status};
    }
    return {problems: body.problems};
  } catch (e) {
    return {error: e.message};
  }
}

// the repository that a problem found by otterdog is about, e.g. 'my-repo' for
// 'repository[name="my-repo"] has ...', 'repo_ruleset[name="main", repository=my-repo] has ...' or
// 'repositories[name="my-repo"] has ...'
const REPOSITORY = /\brepositor(?:y|ies)(?:\[name="([^"]*)"|=([^,\]]*))/;

// the header of a message of otterdog, naming the object it is about and the one containing it: the header of the
// object, e.g. 'repo_ruleset[name="main", repository=my-repo]', 'repository[name="my-repo"]' or 'settings', or its
// path in the configuration, e.g. 'repositories[name="my-repo"].rulesets[name="main"]'
const HEADER = /^\w+(?:\[[^\]]*\])?(?:\.\w+(?:\[[^\]]*\])?)*/;
// the named objects of a header, their kind, e.g. 'repo_ruleset' or 'rulesets', and their name, with the kind and the
// name of the object containing the object in the header of an object
const NAMES = /(\w+)\[\w+="([^"]*)"(?:, (\w+)=([^\]]*))?\]/g;

// Returns the diagnostics of the problems {severity, message} found by otterdog in the configuration of an
// organization: their messages are about the objects of the evaluated configuration, they are located at the property
// they are about, e.g. 'include_refs' in `repo_ruleset[name="main", repository=my-repo] has an invalid 'include_refs'
// pattern '1.2.x'`, at its invalid value if it is quoted, otherwise at the call creating the repository they are about,
// otherwise at the call creating the organization.
export function otterdogDiagnostics(problems, code) {
  const call = mainCall(code) ?? {from: 0, to: 0};
  const properties = problems.length === 0 ? [] : propertiesOf(code);
  return problems.flatMap(({severity, message}) => {
    const located = propertiesAbout(message, code, properties);
    if (located.length > 0) {
      return located.map(({from, to}) => ({from, to, severity, source: "otterdog", message}));
    }
    const match = REPOSITORY.exec(message);
    const {from, to} = (match === null ? null : repositoryCall(code, match[1] ?? match[2])) ?? call;
    return [{from, to, severity, source: "otterdog", message}];
  });
}

// The ranges of the properties of the code that a message is about: the first property quoted in the message, e.g.
// 'include_refs', or the path of a property of a nested object, e.g. 'required_pull_request.allowed_merge_methods', set
// in the object of its header, narrowed to the values of its value that are quoted next, e.g. '1.2.x'. None if the
// property is not set in the code, e.g. inherited from the default configuration.
function propertiesAbout(message, code, properties) {
  const header = HEADER.exec(message);
  if (header === null) {
    return [];
  }
  const names = [...header[0].matchAll(NAMES)];
  const [last, previous] = [names.at(-1), names.at(-2)];
  const object = {
    kind: last?.[1],
    name: last?.[2],
    parent: last?.[3] === undefined ? previous && {kind: previous[1], name: previous[2]} : {kind: last[3], name: last[4]},
  };
  const quoted = [...message.slice(header[0].length).matchAll(/'([^']*)'/g)].map((match) => match[1]);
  for (const [index, quote] of quoted.entries()) {
    const path = quote.split(".");
    const matching = properties.filter((property) => endsWith(property.path, path) && isAbout(property, object));
    if (matching.length > 0) {
      return matching.flatMap((property) => valuesOf(property, code, quoted[index + 1]));
    }
  }
  return [];
}

// Whether a property is set in the object {kind, name, parent} of a header: the object created by a call of a function
// creating objects of its kind with its name, within the innermost object of the kind of the object containing it
// having its name, e.g. a ruleset of a repository rather than of another one within an organization named like the
// repository, or the organization for an object without name, e.g. its settings.
function isAbout(property, {kind, name, parent}) {
  if (name === undefined) {
    return property.function === "newOrg" && property.within.length === 0;
  }
  return property.firstArgument === name && createsKind(property.function, kind)
    && (parent === undefined || property.within.find((call) => createsKind(call.function, parent.kind))?.firstArgument === parent.name);
}

// Whether a function creates the objects of a kind, the kind of an object in the header of otterdog or in the path of
// the configuration: the words of the function end with the ones of the kind, e.g. `newRepoRuleset` for 'repo_ruleset'
// or 'rulesets', and `newRepo`, `extendRepo` or a function of the configuration like `newBinaryRepo` for 'repository'
// or 'repositories', but not `newTeam` for 'repository'.
export function createsKind(name, kind) {
  const words = name.replace(/^(new|extend)/, "").split(/(?=[A-Z])/).map((word) => word.toLowerCase());
  const kindWords = kind.replace(/ies$/, "y").replace(/s$/, "").replace(/^repository$/, "repo").split("_");
  return kindWords.length <= words.length && kindWords.every((word, index) => word === words[words.length - kindWords.length + index]);
}

// The ranges of the literal values of the value of a property quoted as a value, e.g. a string of a list, a number or a
// boolean, the range of the property if there is none.
function valuesOf(property, code, value) {
  const offset = property.from;
  // the first token is the name of the property, the strings are quoted by their value, the other literals as written
  const quotedAs = (token) => (token.type === "string" ? literalValue(token.text) : token.text);
  const values = value === undefined ? [] : tokenize(code.slice(property.from, property.to)).slice(1)
    .filter((token) => ["string", "word"].includes(token.type) && quotedAs(token) === value)
    .map((token) => ({from: offset + token.start, to: offset + token.end}));
  return values.length > 0 ? values : [{from: property.from, to: property.to}];
}

function describe(problem, value) {
  const path = formatPath(value, problem.path);
  const message = problem.severity === "warning" ? problem.message + ", ignored by otterdog" : problem.message;
  return path === "" ? message : path + ": " + message;
}

// Returns the literal properties of the code that a problem is about, see literalProperties: the ones setting the
// invalid property in an object created by a call for the object containing it, e.g. 'has_wiki' of a repository
// rather than of the organization, within the calls creating the objects containing it, e.g. a ruleset 'main' of the
// repository 'a' rather than of the repository 'b', to the invalid value if it can be read.
export function literalsOf(problem, value, literals) {
  // a value of a list, e.g. a topic, is set by the property of the list
  let end = problem.path.length;
  while (end > 0 && typeof problem.path[end - 1] === "number") {
    end--;
  }
  const path = problem.path.slice(0, end);
  const invalid = JSON.stringify(valueAt(value, path));

  return literals.filter((literal) => {
    if (!endsWith(path, literal.path)) {
      return false;
    }
    // the object that the call of the literal would have created
    const objectPath = path.slice(0, path.length - literal.path.length);
    const read = literalValue(literal.value);
    return createdBy(literal, objectPath, value, problem.refs)
      && isWithin(literal.within, objectPath, value, problem.refs)
      && (read === undefined || JSON.stringify(read) === invalid);
  });
}

// Whether the object at a path can have been created by a call: validated with the schema of the objects that its
// function creates, see validate, if it is known, e.g. for newRepo but not for a function of the configuration, and
// having the name passed to the call if it is named.
function createdBy(call, path, value, refs) {
  const schema = schemaOfFunction(call.function);
  return (schema === null || refs.some((ref) => ref.ref === schema && samePath(ref.path, path)))
    && hasName(valueAt(value, path), call.firstArgument);
}

// Whether the object at a path is within the objects created by calls, innermost first: the nearest object containing
// it that was validated with the schema of the objects of a call, if any, has the name passed to the call.
function isWithin(calls, path, value, refs) {
  let inner = path;
  for (const call of calls) {
    const schema = schemaOfFunction(call.function);
    const ref = refs.findLast((r) => r.ref === schema && r.path.length < inner.length && startsWith(inner, r.path));
    if (ref !== undefined) {
      if (!hasName(valueAt(value, ref.path), call.firstArgument)) {
        return false;
      }
      inner = ref.path;
    }
  }
  return true;
}

const hasName = (object, name) => name === undefined || !isObject(object) || !("name" in object) || object.name === name;

const valueAt = (value, path) => path.reduce((parent, key) => parent?.[key], value);

// whether a path ends with another one, e.g. the path of a property in an object created by a function
const endsWith = (path, end) => end.length <= path.length && end.every((key, index) => key === path[path.length - end.length + index]);
const startsWith = (path, start) => start.length <= path.length && start.every((key, index) => key === path[index]);
const samePath = (path, other) => path.length === other.length && startsWith(path, other);

// the number of errors and warnings, showing them when clicked
function noteOf(problems, showProblems) {
  if (problems.length === 0) {
    return null;
  }
  const errors = problems.filter((problem) => problem.severity === "error").length;
  const counts = [[errors, "schema error"], [problems.length - errors, "schema warning"]]
    .filter(([count]) => count > 0)
    .map(([count, label]) => count + " " + label + (count > 1 ? "s" : ""));
  const note = actionLink(counts.join(", "), errors > 0 ? "link-danger" : "link-warning", showProblems);
  note.title = "Problems found with the JSON schema of otterdog, which validates configurations before applying them."
    + " Click to list them.";
  return note;
}

// The state of the validation by otterdog, and the number of its problems by severity, showing them when clicked,
// followed by the link to its limitations.
function validationNote(validated, showProblems, limitationsUrl) {
  if (validated.pending) {
    const note = element("span", "", "validating…");
    note.prepend(element("span", "spinner-border spinner-border-sm me-1"));
    return note;
  }
  if (validated.error !== undefined) {
    return element("span", "text-danger", "validation failed: " + validated.error);
  }

  const note = element("span");
  if (validated.problems.length === 0) {
    // not "valid": otterdog may still find problems in the pull request, see the limitations
    const result = element("span", "text-success", " no problem found by otterdog");
    result.prepend(icon("fas fa-check"));
    note.append(result);
  } else {
    const severities = ["error", "warning", "info"];
    const counts = severities
      .map((severity) => [validated.problems.filter((problem) => problem.severity === severity).length, severity])
      .filter(([count]) => count > 0)
      .map(([count, severity]) => count + " validation " + severity + (count > 1 ? "s" : ""));
    const result = actionLink(counts.join(", "), linkClassOf(validated.problems), showProblems);
    result.title = "Problems found by otterdog. Click to list them.";
    note.append(result);
  }
  note.append(limitationsLink(limitationsUrl));
  return note;
}

// the class of the link to the problems, by their most severe one
function linkClassOf(problems) {
  if (problems.some((problem) => problem.severity === "error")) {
    return "link-danger";
  }
  if (problems.some((problem) => problem.severity === "warning")) {
    return "link-warning";
  }
  return "link-secondary";
}

function limitationsLink(url) {
  const link = element("a", "playground-validation-limitations link-secondary ms-1");
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener";
  link.title = "Limited validation. " + VALIDATION_LIMITATIONS + " Click for the details.";
  link.setAttribute("aria-label", "Limitations of the validation by otterdog");
  link.append(icon("fas fa-circle-info"));
  return link;
}
