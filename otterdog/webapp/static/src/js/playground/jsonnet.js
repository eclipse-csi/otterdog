// A light analysis of the jsonnet code of the playground, tolerating the incomplete code being typed: its tokens, the
// local definitions at its start, and the objects created by a function of the default configuration of otterdog (its
// base_template, e.g. otterdog-defaults), e.g. `orgs.newRepo(...)`, with the properties that have a literal value,
// including the ones of nested objects extended with `+:`. It only follows the brackets and the fields of the
// objects, which is enough to complete their properties and to compare their values with the default configuration.

// the tokens, tried in this order at each position: strings and text blocks, which may not be terminated yet, comments,
// words (identifiers, keywords and numbers), whitespace and single characters
const TOKENS = [
  ["string", /'(?:[^'\\]|\\[\s\S])*'?/y],
  ["string", /"(?:[^"\\]|\\[\s\S])*"?/y],
  ["string", /@'(?:[^']|'')*'?/y],
  ["string", /@"(?:[^"]|"")*"?/y],
  ["string", /\|\|\|[\s\S]*?(?:\|\|\||$)/y],
  ["comment", /(?:\/\/|#)[^\n]*/y],
  ["comment", /\/\*[\s\S]*?(?:\*\/|$)/y],
  ["word", /[A-Za-z0-9_$]+/y],
  ["space", /\s+/y],
  ["punct", /[\s\S]/y],
];

const LITERAL_WORD = /^(?:true|false|null|\d[\w.]*)$/;
const LITERAL_PUNCTUATION = "{}[],:-.";

const isPunctuation = (token, characters) => token.type === "punct" && characters.includes(token.text);

const BRACKET_DEPTHS = {"{": 1, "[": 1, "(": 1, "}": -1, "]": -1, ")": -1};

// the tokens of the code, without its whitespace and comments: {type, text, start, end}
export function tokenize(code) {
  const tokens = [];
  for (let start = 0; start < code.length;) {
    const [type, text] = tokenAt(code, start);
    if (type !== "space" && type !== "comment") {
      tokens.push({type, text, start, end: start + text.length});
    }
    start += text.length;
  }
  return tokens;
}

function tokenAt(code, start) {
  for (const [type, pattern] of TOKENS) {
    pattern.lastIndex = start;
    const match = pattern.exec(code);
    if (match !== null) {
      return [type, match[0]];
    }
  }
  throw new Error("no token at " + start);
}

const IMPORT_KEYWORDS = new Set(["import", "importstr", "importbin"]);
// the start of a string that can be imported, quoted or verbatim, jsonnet not allowing to import a text block
const IMPORTED_STRING = /^@?(['"])/;

// Returns the imports of the code, e.g. `import 'a.libsonnet'`, without the text of its strings and comments that
// looks like an import: {keyword, path, from, to}, path being the imported path as written, from and to its range in
// the code, inside the quotes.
export function importsOf(code) {
  const tokens = tokenize(code);
  const imports = [];
  for (const [index, token] of tokens.entries()) {
    const path = token.type === "word" && IMPORT_KEYWORDS.has(token.text) ? importedPath(tokens[index + 1]) : null;
    if (path !== null) {
      imports.push({keyword: token.text, ...path});
    }
  }
  return imports;
}

// the path {path, from, to} imported by a string token, null if it cannot be imported or is not terminated yet
function importedPath(string) {
  const quote = string?.type === "string" ? IMPORTED_STRING.exec(string.text) : null;
  if (quote === null || string.text.length === quote[0].length || !string.text.endsWith(quote[1])) {
    return null;
  }
  return {path: string.text.slice(quote[0].length, -1), from: string.start + quote[0].length, to: string.end - 1};
}

// Returns the code with the path of each of its imports, see importsOf, replaced by the path returned by
// rewrite(import).
export function rewriteImports(code, rewrite) {
  let rewritten = "";
  let end = 0;
  for (const imported of importsOf(code)) {
    rewritten += code.slice(end, imported.from) + rewrite(imported);
    end = imported.to;
  }
  return rewritten + code.slice(end);
}

// Returns the properties with a literal value of the objects created by a function of the default configuration:
// {function, call, exact, firstArgument, path, value, from, to, within}, see callBefore for the call, path being the
// path of the property in the returned object, value its literal value, from and to the range of the property in the
// code, and within the calls {function, firstArgument} creating the objects that contain the object, innermost first,
// e.g. `orgs.newRepo('my-repo')` for a ruleset of the repository.
export function literalProperties(code) {
  return scan(code).values;
}

// Returns the properties of the objects created by a function of the default configuration, whatever their value and
// operator, e.g. `include_refs+: [...]`: {function, call, exact, firstArgument, path, from, to, within}, see
// literalProperties, from and to being the range of the property, from its name to the end of its value.
export function propertiesOf(code) {
  return scan(code).properties;
}

// the literal properties whose values can be compared with the default configuration
export function explicitValues(code) {
  return literalProperties(code).filter((property) => property.exact);
}

// Returns the call of a function of the default configuration by the expression of the code, e.g.
// `orgs.newOrg('my-project', 'my-org') {...}`, as {name, from, to}, name being the name of the function, e.g. 'newOrg',
// and from and to the range of `orgs.newOrg` in the code, null if the expression is not such a call.
export function mainCall(code) {
  const {text, names} = topLevelLocals(code);
  const [alias, dot, name, open] = tokenize(code.slice(text.length));
  if (!names.includes(alias?.text) || !isFunctionOf(alias, dot, name) || open?.text !== "(") {
    return null;
  }
  return {name: name.text, from: text.length + alias.start, to: text.length + name.end};
}

// Returns the range {from, to} of the call creating a repository in the code, e.g. `orgs.newRepo('my-repo')`, null if
// it is not found: the first call of a function whose name contains "repo", e.g. `newRepo`, `extendRepo` or a function
// of the configuration like `newBinaryRepo`, with the name of the repository as first argument.
export function repositoryCall(code, name) {
  const tokens = tokenize(code);
  const index = tokens.findIndex((token, at) => token.type === "string" && tokens[at - 1]?.text === "("
    && /repo/i.test(tokens[at - 2]?.text ?? "") && literalValue(token.text) === name);
  if (index === -1) {
    return null;
  }
  const [alias, dot, call] = [tokens[index - 4], tokens[index - 3], tokens[index - 2]];
  const end = tokens[index + 1]?.text === ")" ? tokens[index + 1] : tokens[index];
  return {from: isFunctionOf(alias, dot, call) ? alias.start : call.start, to: end.end};
}

// the value of a literal, e.g. 1 for `1` or "my-repo" for `'my-repo'`, undefined if it cannot be read as json, e.g. an
// object with unquoted names
export function literalValue(text) {
  // a single-quoted string is read as the same double-quoted string
  const doubleQuoted = (content) => content.replaceAll(String.raw`\'`, "'").replaceAll('"', String.raw`\"`);
  const json = text.replace(/^'(.*)'$/s, (string, content) => '"' + doubleQuoted(content) + '"');
  try {
    return JSON.parse(json);
  } catch {
    return undefined;
  }
}

// Returns the context of a completion at an offset of the code: {kind: "function", alias, word, from} after the
// alias of the default configuration, e.g. 'orgs.new', or {kind: "property", scope, word, from} at the name of a
// property of an object created by a function of the default configuration, null otherwise.
export function completionContext(code, offset) {
  const prefix = code.slice(0, offset);
  const word = nameBefore(prefix);
  const from = offset - word.length;
  const alias = aliasBefore(prefix.slice(0, from));
  if (alias !== "") {
    // the functions of a local definition, e.g. the import of the default configuration, not the ones of std
    return topLevelLocals(prefix).names.includes(alias) ? {kind: "function", alias, word, from} : null;
  }

  const scope = fieldScope(prefix.slice(0, from));
  return scope === null ? null : {kind: "property", scope, word, from};
}

// the name at the end of a text, e.g. 'newR' for 'orgs.newR', scanning it backwards
function nameBefore(text) {
  let start = text.length;
  while (start > 0 && /[\w$]/.test(text[start - 1])) {
    start--;
  }
  // a name does not start with a digit
  return text.slice(start).replace(/^\d+/, "");
}

// the name before a dot at the end of a text, e.g. 'orgs' for 'orgs.', empty if the text does not end with a dot
function aliasBefore(text) {
  const beforeDot = text.trimEnd();
  return beforeDot.endsWith(".") ? nameBefore(beforeDot.slice(0, -1).trimEnd()) : "";
}

// the scope of the object whose next field starts at the end of the code, null if no field starts there
function fieldScope(code) {
  const frames = scan(code).frames;
  const frame = frames.at(-1);
  return frame?.scope && frame.expectsField ? frame.scope : null;
}

// Returns the local definitions at the start of the code, {text, names}: the import of the default configuration,
// but also the objects extending it and the functions of the configuration, e.g.
// `local orgs = (import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet') + {...};`, which the expressions
// evaluated for the completion and the default values may use.
export function topLevelLocals(code) {
  const tokens = tokenize(code);
  // the local definitions whose ';' has not been reached yet: the top-level one and the ones of its value, e.g. the
  // locals of the body of a function
  const state = {names: [], depth: 0, pending: 0, end: 0};
  for (const [index, token] of tokens.entries()) {
    if (state.depth === 0 && state.pending === 0 && token.text !== "local") {
      break;
    }
    readTopLevel(state, token, tokens[index + 1]);
  }
  return {text: code.slice(0, state.end), names: state.names};
}

// follows the definitions at the top level of the code: their names, and the end of the last one
function readTopLevel(state, token, next) {
  if (state.depth === 0) {
    if (isTopLevelName(token, state.pending)) {
      state.names.push(next?.text);
    }
    state.pending += {local: 1, ";": -1}[token.text] ?? 0;
    state.end = state.pending === 0 && token.text === ";" ? token.end : state.end;
  }
  state.depth += BRACKET_DEPTHS[token.text] ?? 0;
}

// the name of a top-level definition follows 'local', or a comma separating several definitions
const isTopLevelName = (token, pending) => (token.text === "local" && pending === 0) || (token.text === "," && pending === 1);

// scans the objects of the code: their properties, the literal values of their properties, and the brackets still
// open at its end
function scan(code) {
  const tokens = tokenize(code);
  const values = [];
  const properties = [];
  // the open brackets, an object created by a function or extending one of them has a scope {call, path}, and the
  // calls creating the objects containing a bracket are its calls, innermost first
  const frames = [];

  tokens.forEach((token, index) => {
    const frame = frames.at(-1);
    if (isPunctuation(token, "{[(")) {
      const scope = token.text === "{" ? scopeOf(code, tokens, index, frame) : null;
      const calls = scope?.path.length === 0 ? [scope, ...(frame?.calls ?? [])] : (frame?.calls ?? []);
      frames.push({scope, field: null, expectsField: true, calls});
    } else if (isPunctuation(token, "}])")) {
      endField(code, tokens, frames.pop(), index, values, properties);
    } else if (frame?.scope) {
      readField(code, tokens, frame, index, values, properties);
    }
  });
  return {values, properties, frames};
}

// reads the fields of an object scope, separated by commas
function readField(code, tokens, frame, index, values, properties) {
  if (tokens[index].text === ",") {
    endField(code, tokens, frame, index, values, properties);
    frame.expectsField = true;
  } else if (frame.expectsField) {
    frame.field = fieldAt(tokens, index);
    frame.expectsField = false;
  }
}

// the scope of an object: created by a function of the default configuration, or extending a property of one
function scopeOf(code, tokens, index, frame) {
  const call = callBefore(code, tokens, index);
  if (call !== null) {
    return {...call, path: []};
  }
  const field = frame?.field;
  if (frame?.scope && field?.operator === "+:" && field.valueIndex === index) {
    return {...frame.scope, path: [...frame.scope.path, field.name]};
  }
  return null;
}

// The call of a function of the default configuration before an object, e.g. `orgs.newRepo('my-repo')`, as
// {function, call, exact, firstArgument}, function being the name of the called function, e.g. 'newRepo'. A call that cannot be evaluated as is, e.g. `orgs.newRepo(name)` in a function of the
// configuration, or that only extends an object, e.g. `orgs.extendRepo('my-repo')`, is replaced by a call returning an
// object with the same properties, e.g. `orgs.newRepo('playground')`: it is not exact, its values are not compared with
// the default configuration. firstArgument is the value of the first argument if it is literal, e.g. the name of a
// repository, undefined otherwise.
function callBefore(code, tokens, index) {
  if (tokens[index - 1]?.text !== ")") {
    return null;
  }
  const open = openingParenthesis(tokens, index - 1);
  const [alias, dot, name] = [tokens[open - 3], tokens[open - 2], tokens[open - 1]];
  if (!isFunctionOf(alias, dot, name)) {
    return null;
  }
  const args = argumentsOf(code, tokens.slice(open + 1, index - 1));
  const exact = name.text.startsWith("new") && args.every((argument) => argument.literal);
  const first = args.find((argument) => !argument.named);
  const firstArgument = first?.literal ? literalValue(first.text) : undefined;
  return {function: name.text, call: alias.text + "." + callOf(name.text, args), exact, firstArgument};
}

// a function of a local definition, e.g. `orgs.newRepo`
const isFunctionOf = (alias, dot, name) => alias?.type === "word" && dot?.text === "." && name?.type === "word";

// the call of a function returning the object, with placeholders for the arguments that are not literal
function callOf(name, args) {
  const positional = args.filter((argument) => !argument.named);
  const values = positional.map((argument) => (argument.literal ? argument.text : "'playground'"));
  return name.replace(/^extend/, "new") + "(" + values.join(", ") + ")";
}

// the arguments of a call: their text, whether they are literal, and whether they are named, e.g. `org=$`
function argumentsOf(code, tokens) {
  const args = [[]];
  let depth = 0;
  for (const token of tokens) {
    if (depth === 0 && token.text === ",") {
      args.push([]);
    } else {
      depth += BRACKET_DEPTHS[token.text] ?? 0;
      args.at(-1).push(token);
    }
  }
  return args.filter((argument) => argument.length > 0).map((argument) => ({
    text: code.slice(argument[0].start, argument.at(-1).end),
    literal: isLiteral(argument),
    named: argument[1]?.text === "=",
  }));
}

function openingParenthesis(tokens, close) {
  let depth = 0;
  for (let index = close; index >= 0; index--) {
    depth += {")": 1, "(": -1}[tokens[index].text] ?? 0;
    if (depth === 0) {
      return index;
    }
  }
  return -1;
}

// a property at the start of a field: its name, its operator, e.g. ':' or '+:', and the index of its value
function fieldAt(tokens, index) {
  const name = tokens[index];
  let next = index + 1;
  while (next < tokens.length && isPunctuation(tokens[next], "+:")) {
    next++;
  }
  const operator = tokens.slice(index + 1, next).map((token) => token.text).join("");
  const isProperty = ["word", "string"].includes(name.type) && !["local", "assert"].includes(name.text);
  return isProperty && operator !== ""
    ? {name: name.text.replace(/^['"]|['"]$/g, ""), operator, start: name.start, valueIndex: next}
    : null;
}

function endField(code, tokens, frame, end, values, properties) {
  const field = frame?.field;
  if (!frame?.scope || !field) {
    return;
  }
  const valueTokens = tokens.slice(field.valueIndex, end);
  if (valueTokens.length > 0) {
    const to = valueTokens[valueTokens.length - 1].end;
    const path = [...frame.scope.path, field.name];
    const within = frame.calls.slice(1).map((call) => ({function: call.function, firstArgument: call.firstArgument}));
    properties.push({...frame.scope, path, from: field.start, to, within});
    if (field.operator === ":" && isLiteral(valueTokens)) {
      values.push({...frame.scope, path, value: code.slice(valueTokens[0].start, to), from: field.start, to, within});
    }
  }
  frame.field = null;
}

// a literal value: strings, numbers, booleans, null, and lists or objects of them
function isLiteral(tokens) {
  return tokens.length > 0 && tokens.every((token, index) => isLiteralToken(token, tokens[index + 1]));
}

// words are literal values or the names of the properties of an object
function isLiteralToken(token, next) {
  if (token.type === "word") {
    return LITERAL_WORD.test(token.text) || next?.text === ":";
  }
  return token.type === "string" || isPunctuation(token, LITERAL_PUNCTUATION);
}
