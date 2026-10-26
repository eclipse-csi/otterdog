import {setDiagnostics} from "@codemirror/lint";

import {actionLink} from "./dom.js";
import {literalProperties, literalValue, mainCall} from "./jsonnet.js";
import {formatPath, schemaOfFunction, validate} from "./schema.js";
import {isObject} from "./values.js";

// The problems of the evaluated value of the shown document for the JSON schemas of otterdog, see schema.js, e.g. a
// string instead of a number, which otterdog rejects, or an unknown property, which otterdog ignores. The value is
// validated if the document calls a function of the default configuration, e.g. `orgs.newOrg(...)`. The problems are
// reported as diagnostics of the editor, at the literal values they are about, otherwise at this call.
//
// Returns the functions showing the problems of a document for its value, and clearing them, with dispatch(d, spec)
// applying a transaction to a document. showNote is called with the document and the note telling the number of
// problems, null if none, which shows them with showProblems when clicked.
export function createValidation({schemas, dispatch, showProblems, showNote}) {
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
    dispatch(d, setDiagnostics(d.state, diagnostics));
    showNote(d, noteOf(problems, showProblems));
  }

  function clear(d) {
    dispatch(d, setDiagnostics(d.state, []));
  }

  return {show, clear};
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
