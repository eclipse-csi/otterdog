// Explicit values of a snippet that are identical to the values of the default configuration of otterdog (its
// base_template, e.g. otterdog-defaults), e.g. `has_wiki: true` in `orgs.newRepo('my-repo') { has_wiki: true }` while
// `orgs.newRepo` already returns `has_wiki: true`: such a line can be removed, the value is inherited. The defaults of
// GitHub are not taken into account, otterdog applies the values of its default configuration.
//
// The snippet is scanned for the objects created by a function of the default configuration, e.g. `orgs.newRepo(...)`,
// and for their properties that have a literal value, including the ones of nested objects extended with `+:`. Each of
// them is compared to the same property of the object returned by the function, by evaluating the snippet built by
// defaultsSnippet with the default configuration.

// strings and text blocks, comments, words (identifiers, keywords and numbers), whitespace and single characters
const TOKEN = /'(?:[^'\\]|\\[\s\S])*'?|"(?:[^"\\]|\\[\s\S])*"?|@'(?:[^']|'')*'?|@"(?:[^"]|"")*"?|\|\|\|[\s\S]*?(?:\|\|\||$)|\/\/[^\n]*|#[^\n]*|\/\*[\s\S]*?(?:\*\/|$)|[A-Za-z0-9_$]+|\s+|[\s\S]/y;

const LITERAL_WORD = /^(?:true|false|null|\d[\w.]*)$/;
const LITERAL_PUNCTUATION = "{}[],:-.";

const isPunctuation = (token, characters) => token.type === "punct" && characters.includes(token.text);

export function tokenize(code) {
  const tokens = [];
  TOKEN.lastIndex = 0;
  for (let match = TOKEN.exec(code); match !== null && match[0] !== ""; match = TOKEN.exec(code)) {
    const type = tokenType(match[0]);
    if (type !== "space" && type !== "comment") {
      tokens.push({type, text: match[0], start: match.index, end: TOKEN.lastIndex});
    }
  }
  return tokens;
}

function tokenType(text) {
  if (/^\s/.test(text)) {
    return "space";
  }
  if (/^(?:\/\/|#|\/\*)/.test(text)) {
    return "comment";
  }
  if (/^(?:['"@]|\|\|\|)/.test(text)) {
    return "string";
  }
  return /^[A-Za-z0-9_$]/.test(text) ? "word" : "punct";
}

// Returns the properties with a literal value of the objects created by a function of the default configuration:
// {call, path, value, from, to}, call being the call of the function, e.g. `orgs.newRepo('my-repo')`, path the path of
// the property in the returned object, and from and to the range of the property in the code.
export function explicitValues(code) {
  const tokens = tokenize(code);
  const values = [];
  // the open brackets, an object created by a function or extending one of them has a scope {call, path}
  const frames = [];

  tokens.forEach((token, index) => {
    const frame = frames[frames.length - 1];
    if (isPunctuation(token, "{[(")) {
      const scope = token.text === "{" ? scopeOf(code, tokens, index, frame) : null;
      frames.push({scope, field: null, expectsField: true});
    } else if (isPunctuation(token, "}])")) {
      endField(code, tokens, frames.pop(), index, values);
    } else if (frame?.scope) {
      readField(code, tokens, frame, index, values);
    }
  });
  return values;
}

// reads the fields of an object scope, separated by commas
function readField(code, tokens, frame, index, values) {
  if (tokens[index].text === ",") {
    endField(code, tokens, frame, index, values);
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
    return {call, path: []};
  }
  const field = frame?.field;
  if (frame?.scope && field?.operator === "+:" && field.valueIndex === index) {
    return {call: frame.scope.call, path: [...frame.scope.path, field.name]};
  }
  return null;
}

// the call of a function of the default configuration before an object, e.g. `orgs.newRepo('my-repo')`, with literal
// arguments only
function callBefore(code, tokens, index) {
  if (tokens[index - 1]?.text !== ")") {
    return null;
  }
  const open = openingParenthesis(tokens, index - 1);
  const [alias, dot, name] = [tokens[open - 3], tokens[open - 2], tokens[open - 1]];
  const isCall = alias?.type === "word" && dot?.text === "." && /^new/.test(name?.text);
  return isCall && isLiteral(tokens.slice(open + 1, index - 1), true) ? code.slice(alias.start, tokens[index - 1].end) : null;
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

function endField(code, tokens, frame, end, values) {
  const field = frame?.field;
  if (!frame?.scope || field?.operator !== ":") {
    return;
  }
  const valueTokens = tokens.slice(field.valueIndex, end);
  if (valueTokens.length > 0 && isLiteral(valueTokens, false)) {
    const to = valueTokens[valueTokens.length - 1].end;
    values.push({...frame.scope, path: [...frame.scope.path, field.name], value: code.slice(valueTokens[0].start, to), from: field.start, to});
  }
  frame.field = null;
}

// a literal value: strings, numbers, booleans, null, and lists or objects of them
function isLiteral(tokens, allowEmpty) {
  return (allowEmpty || tokens.length > 0) && tokens.every((token, index) => isLiteralToken(token, tokens[index + 1]));
}

// words are literal values or the names of the properties of an object
function isLiteralToken(token, next) {
  if (token.type === "word") {
    return LITERAL_WORD.test(token.text) || next?.text === ":";
  }
  return token.type === "string" || isPunctuation(token, LITERAL_PUNCTUATION);
}

// Returns the snippet evaluating whether each explicit value is identical to the value of the default configuration,
// as a list of booleans, null if there is no value to compare.
export function defaultsSnippet(code, values) {
  if (values.length === 0) {
    return null;
  }

  const imports = [...code.matchAll(/^[ \t]*local\s+[A-Za-z_]\w*\s*=\s*import\s+(?:'[^'\n]*'|"[^"\n]*")\s*;/gm)];
  return [
    ...imports.map((match) => match[0].trim()),
    "local defaultsHas(object, path) = std.length(path) == 0"
      + " || (std.isObject(object) && std.objectHasAll(object, path[0]) && defaultsHas(object[path[0]], path[1:]));",
    "local defaultsSame(object, path, value) ="
      + " defaultsHas(object, path) && std.foldl(function(result, key) result[key], path, object) == value;",
    "[",
    ...values.map((value) => "  defaultsSame(" + value.call + ", " + JSON.stringify(value.path) + ", " + value.value + "),"),
    "]",
  ].join("\n");
}
