// The snippets evaluated by the playground: shared in links, prepared to be evaluated and located by errors.

export const MAIN_FILE = "playground.jsonnet";

// length of the snippets accepted as '#code=<base64url>' in the url
export const MAX_ENCODED_SNIPPET = 200000;

// locations of go-jsonnet, e.g. 'playground.jsonnet:5:8-25' or 'playground.jsonnet:(5:8)-(6:13)', the lines and
// columns starting at 1, the end column being excluded
const ERROR_LOCATION = /([^\s:()<>]+\.(?:jsonnet|libsonnet)):(?:(\d+):(\d+)(?:-(\d+))?|\((\d+):(\d+)\)-\((\d+):(\d+)\))/g;

export const baseName = (path) => path.split("/").pop();

export function encodeSnippet(code) {
  const bytes = new TextEncoder().encode(code);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCodePoint(...bytes.subarray(index, index + 0x8000));
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// Returns the snippet passed as '#code=<base64url>' in the url, e.g. by a link of the documentation.
// The snippet is only decoded in the browser and set as plain text, it is never sent to the server.
export function snippetOfHash(hash) {
  const match = /^#code=([A-Za-z0-9_-]+)$/.exec(hash);
  if (match === null || match[1].length > MAX_ENCODED_SNIPPET) {
    return null;
  }

  try {
    return decodeSnippet(match[1]);
  } catch (e) {
    console.warn("failed to decode the snippet passed in the url", e);
    return null;
  }
}

function decodeSnippet(encoded) {
  const base64 = encoded.replaceAll("-", "+").replaceAll("_", "/");
  const padded = base64 + "=".repeat((4 - base64.length % 4) % 4);
  const bytes = Uint8Array.from(atob(padded), (c) => c.codePointAt(0));
  return new TextDecoder("utf-8", {fatal: true}).decode(bytes);
}

// Prepares a snippet to be evaluated with the files of the playground: maps imports of a default configuration
// to these files, and imports the default configuration if the snippet does not.
export function normalizeSnippet(code, templateFiles, defaultConfig) {
  code = code.replace(/import\s+'vendor\/[^'/]+\/([^'/]+)'/g, (statement, name) => {
    const file = templateFiles.find((f) => f.endsWith("/" + name));
    return file === undefined ? statement : "import '" + file + "'";
  });

  if (!/\bimport\s+'/.test(code)) {
    code = "local orgs = import '" + defaultConfig + "';\n\n" + code;
  }
  // without trailing empty lines, the content of the editor being compared to it
  return code.replace(/\s+$/, "");
}

// Returns the locations of an error message: {file, from, to, index, text}, the positions being the ones of CodeMirror.
export function errorLocations(message) {
  return [...message.matchAll(ERROR_LOCATION)].map((match) => ({
    // further imports of a path are spelled './<path>', '././<path>', ... (see jsonnet-worker.js)
    file: match[1].replace(/^(\.\/)+/, ""),
    ...rangeOf(match),
    index: match.index,
    text: match[0],
  }));
}

const position = (line, column) => ({line: line - 1, ch: column - 1});

function rangeOf([, , line, column, endColumn, fromLine, fromColumn, toLine, toColumn]) {
  if (line === undefined) {
    return {from: position(fromLine, fromColumn), to: position(toLine, toColumn)};
  }
  // a column without end is a range of one character
  return {from: position(line, column), to: position(line, endColumn ?? +column + 1)};
}
