import {autocompletion, pickedCompletion} from "@codemirror/autocomplete";
import {hoverTooltip} from "@codemirror/view";

import {completionContext, topLevelLocals} from "./jsonnet.js";
import {tooltipContent} from "./tooltip.js";
import {formatValue, isObject} from "./values.js";

// The playground edits Jsonnet code using a template chosen by the organization.
// A snippet imports that template under an alias, e.g. `local orgs = import ...`.
// Typing `orgs.newR` offers its constructor functions; editing the object returned
// by `orgs.newRepo(...)` offers properties and their default values.
// Evaluate the imported template to discover those functions and defaults, so
// custom templates and functions defined in the snippet are reflected in the UI.
// playground-reference.json supplies the documentation shown beside suggestions
// and when hovering a name.

// delay before describing a hovered name
const HOVER_DELAY = 400;
// evaluations kept for the completion, the local definitions of the code changing while it is edited
const MAX_EVALUATIONS = 50;

// Parameter names are only display hints, e.g. "(name)" next to newRepo.
// Jsonnet can report how many arguments a function requires, but not their names.
// Recognize the common `local newRepo(name) = ...` form without parsing Jsonnet.
// Other forms can still be completed; they simply have no parameter-name hint.
// Process the selected template last so its definitions override library hints.
export function functionParameters(templateFiles, defaultConfig) {
  const selected = templateFiles.find((file) => defaultConfig !== undefined && file.filename === defaultConfig);
  const libraries = templateFiles.filter((file) => file !== selected);
  const ordered = selected === undefined ? libraries : [...libraries, selected];
  const parameters = new Map();
  for (const file of ordered) {
    for (const match of file.content.matchAll(/^[ \t]*local[ \t]+(\w+)[ \t]*\(([^)]*)\)[ \t]*=/gm)) {
      parameters.set(match[1], match[2].trim());
    }
  }
  return parameters;
}

// the reference of the object created by a call and extended along a path, e.g. the workflow settings of a repository
export function referenceOf(reference, scope) {
  let id = reference.functions[/\.(new\w+)\(/.exec(scope.call)?.[1]];
  for (const key of scope.path) {
    id = reference.objects[id]?.properties[key]?.object;
  }
  return reference.objects[id] ?? null;
}

// the text inserted for a property and the position of the cursor in it, depending on its default value
export function propertyInsertion(name, values) {
  if (!Object.hasOwn(values, name)) {
    // hidden properties, e.g. the repositories of an organization
    return {text: name + "+:: ", cursor: 0};
  }
  const value = values[name];
  if (Array.isArray(value)) {
    return {text: name + "+: []", cursor: -1};
  }
  return isObject(value) ? {text: name + "+: {}", cursor: -1} : {text: name + ": ", cursor: 0};
}

// Returns the extensions of the editor completing the names and describing them, see the description of the module.
export function completionExtensions({evaluate, reference, documentationUrl, templateFiles, defaultConfig}) {
  const describe = (info) => tooltipContent(info, documentationUrl);
  const candidates = createCandidates({evaluate, reference, describe, parameters: functionParameters(templateFiles, defaultConfig)});

  // the completions of the name at the cursor, proposed while typing it or after a dot, and with Ctrl+Space
  async function complete(context) {
    const code = context.state.doc.toString();
    const found = completionContext(code, context.pos);
    if (found === null || (found.kind === "property" && found.word === "" && !context.explicit)) {
      return null;
    }
    const options = await candidates(code, found).catch(() => []);
    return {from: found.from, options, validFor: /^[\w$]*$/};
  }

  // a hovered name is described like its completion
  async function describeHovered(view, pos) {
    const word = view.state.wordAt(pos);
    const code = view.state.doc.toString();
    const found = word === null ? null : completionContext(code, word.to);
    const options = found === null ? [] : await candidates(code, found).catch(() => []);
    const option = options.find((candidate) => candidate.label === found.word);
    return option === undefined ? null : {pos: word.from, end: word.to, create: () => ({dom: option.info()})};
  }

  // the completions start with the typed name, like the names of the default configuration they complete
  return [autocompletion({override: [complete], filterStrict: true}), hoverTooltip(describeHovered, {hoverTime: HOVER_DELAY})];
}

// Returns a function resolving to the completions of a context: the functions of the default configuration, or the
// properties of an object created by one of them.
function createCandidates({evaluate, reference, describe, parameters}) {
  const evaluations = new Map();

  // Evaluates an expression with the local definitions of the code, e.g. its import of the default configuration, once.
  // Only the definitions before the completed name are used, the one being edited may not be complete yet, e.g. a
  // function of the configuration.
  function evaluateOnce(code, context, expression) {
    const snippet = topLevelLocals(code.slice(0, context.from)).text + "\n" + expression;
    if (!evaluations.has(snippet)) {
      if (evaluations.size >= MAX_EVALUATIONS) {
        // the oldest one, maps keeping the order of insertion
        evaluations.delete(evaluations.keys().next().value);
      }
      evaluations.set(snippet, evaluate(snippet).then((json) => JSON.parse(json)));
    }
    return evaluations.get(snippet);
  }

  return async (code, context) => {
    if (context.kind === "function") {
      const alias = context.alias;
      // std.length reads the required parameter count from the actual function,
      // so overrides and functions with default arguments need no source parsing.
      const functions = await evaluateOnce(code, context, `[{name: name, required: std.length(${alias}[name])}
for name in std.objectFieldsAll(${alias}) if std.isFunction(${alias}[name])]`);
      return functions.map(({name, required}) => functionCompletion({
        alias, name, parameterLabel: parameters.get(name), requiredArguments: required, reference, describe,
      }));
    }

    const path = JSON.stringify(context.scope.path);
    const defaults = await evaluateOnce(code, context, `local object = std.foldl(function(value, key) value[key], ${path}, ${context.scope.call});
{fields: std.objectFieldsAll(object), values: object}`);
    const object = referenceOf(reference, context.scope);
    return defaults.fields.map((name) => propertyCompletion(name, defaults.values, object, describe));
  };
}

// Build the menu entry, inserted call and tooltip from the same argument count.
// The evaluated function decides whether a value is needed; source labels may
// describe an upstream definition that the custom template has overridden.
export function functionCompletion({alias, name, parameterLabel, requiredArguments, reference, describe}) {
  const needsArgument = requiredArguments > 0;
  const signature = needsArgument ? parameterLabel || "…" : "";
  return {
    label: name,
    detail: "(" + signature + ")",
    type: "function",
    // the cursor is placed in the first argument, e.g. the name of a repository
    apply: insert(needsArgument ? name + "('')" : name + "()", needsArgument ? -2 : 0),
    info: () => describe({
      title: alias + "." + name + "(" + signature + ")",
      description: "Returns a new object with the values of the default configuration, to extend with the properties that differ.",
      source: reference.objects[reference.functions[name]] ?? null,
    }),
  };
}

function propertyCompletion(name, values, object, describe) {
  const {text, cursor} = propertyInsertion(name, values);
  const documented = object?.properties[name];
  const value = Object.hasOwn(values, name) ? formatValue(values[name]) : null;
  return {
    label: name,
    // the default value follows the name
    detail: value === null ? undefined : formatValue(values[name], 40),
    type: "property",
    apply: insert(text, cursor),
    info: () => describe({
      title: name,
      type: documented?.type,
      description: documented?.description ?? null,
      notes: documented?.notes,
      source: object,
      value,
    }),
  };
}

// inserts a text in place of the completed name, the cursor being moved by an offset from its end
function insert(text, cursor) {
  return (view, completion, from, to) => view.dispatch({
    changes: {from, to, insert: text},
    selection: {anchor: from + text.length + cursor},
    annotations: pickedCompletion.of(completion),
    userEvent: "input.complete",
    scrollIntoView: true,
  });
}
