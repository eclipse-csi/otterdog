import {actionLink} from "./dom.js";
import {markField} from "./editors.js";
import {explicitValues, topLevelLocals} from "./jsonnet.js";

// The explicit values of a document that are identical to the values of the default configuration of otterdog (its
// base_template, e.g. otterdog-defaults), e.g. `has_wiki: true` in `orgs.newRepo('my-repo') { has_wiki: true }` while
// `orgs.newRepo` already returns `has_wiki: true`: such a line can be removed, the value is inherited. The defaults of
// GitHub are not taken into account, otterdog applies the values of its default configuration.
//
// The literal values of the objects created by a function of the default configuration, see explicitValues, are
// compared to the same properties of the objects returned by the functions, by evaluating the snippet built by
// defaultsSnippet with the default configuration. The identical values are then checked in their context: the
// document without them must have the same value, which a value computed by the default configuration from other
// properties may change, e.g. the repositories of an organization from its hidden _repositories.

// Returns the extension of the states of the documents marking the values that are identical to the default
// configuration named label, and the functions marking these values of a document and clearing them, with
// dispatch(d, spec) applying a transaction to a document. Once marked, showNote is called with the document and the
// note telling the number of these values, null if there is none, which goes to the next one with goTo when clicked.
export function createDefaultValues({evaluate, label, dispatch, goTo, showNote}) {
  const marks = markField();
  const title = "Same value as in the default configuration " + label + ": this line can be removed, the value is inherited.";

  // highlights the values of the evaluated document, d.result being its evaluation
  async function highlight(d) {
    const {code, value} = d.result;
    if (d.defaultValues !== code) {
      const ranges = await identicalValues(evaluate, code, value);
      if (d.code !== code) {
        // changed meanwhile, highlighted once evaluated again
        return;
      }
      dispatch(d, {effects: marks.set(ranges.map(({from, to}) => ({from, to, className: "playground-default-value", title})))});
      d.defaultValues = code;
    }
    showNote(d, noteOf(d));
  }

  function clear(d) {
    dispatch(d, {effects: marks.set([])});
    d.defaultValues = null;
  }

  // the number of marked values, going to the next one, at its position after the changes of the document
  function noteOf(d) {
    const count = marks.ranges(d.state).length;
    if (count === 0) {
      return null;
    }
    let next = 0;
    const text = count === 1 ? "1 value already set by the default configuration" : count + " values already set by the default configuration";
    const note = actionLink(text, "link-secondary", () => {
      const ranges = marks.ranges(d.state);
      if (ranges.length > 0) {
        goTo(ranges[next++ % ranges.length]);
      }
    });
    note.title = "Values that the default configuration " + label + " already sets, the defaults of GitHub are not taken"
      + " into account: they are inherited, and these lines can be removed. Click to go to the next one.";
    return note;
  }

  return {extension: marks.extension, highlight, clear};
}

// the explicit values of the code that are identical to the default configuration, the code having the value value
async function identicalValues(evaluate, code, value) {
  const values = explicitValues(code);
  const snippet = defaultsSnippet(code, values);
  if (snippet === null) {
    return [];
  }
  let identical;
  try {
    identical = JSON.parse(await evaluate(snippet));
  } catch {
    // e.g. a call of the default configuration that is not supported by the template, nothing is highlighted
    return [];
  }
  return removableValues(evaluate, code, values.filter((v, index) => identical[index] === true), JSON.stringify(value));
}

// Returns the values that can be removed from the code without changing its value, expected being this value as json.
// The values are removed together, then by halves if this changes the value of the code, so that the code is evaluated
// once if all of them can be removed.
export async function removableValues(evaluate, code, values, expected) {
  if (values.length === 0 || await sameValue(evaluate, withoutValues(code, values), expected)) {
    return values;
  }
  if (values.length === 1) {
    return [];
  }
  const half = Math.ceil(values.length / 2);
  const removable = await Promise.all([values.slice(0, half), values.slice(half)].map((part) => removableValues(evaluate, code, part, expected)));
  return removable.flat();
}

async function sameValue(evaluate, code, expected) {
  try {
    return JSON.stringify(JSON.parse(await evaluate(code))) === expected;
  } catch {
    return false;
  }
}

// the code without the fields of values {from, to}, with the comma following them
export function withoutValues(code, values) {
  let result = code;
  for (const {from, to} of [...values].sort((a, b) => b.from - a.from)) {
    const comma = /^\s*,/.exec(result.slice(to));
    result = result.slice(0, from) + result.slice(to + (comma?.[0].length ?? 0));
  }
  return result;
}

// Returns the snippet evaluating whether each explicit value is identical to the value of the default configuration,
// as a list of booleans, null if there is no value to compare.
export function defaultsSnippet(code, values) {
  if (values.length === 0) {
    return null;
  }

  return [
    topLevelLocals(code).text,
    "local defaultsHas(object, path) = std.length(path) == 0"
      + " || (std.isObject(object) && std.objectHasAll(object, path[0]) && defaultsHas(object[path[0]], path[1:]));",
    "local defaultsSame(object, path, value) ="
      + " defaultsHas(object, path) && std.foldl(function(result, key) result[key], path, object) == value;",
    "[",
    ...values.map((value) => "  defaultsSame(" + value.call + ", " + JSON.stringify(value.path) + ", " + value.value + "),"),
    "]",
  ].join("\n");
}
