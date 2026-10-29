// The snippets evaluated by the playground: shared in links, prepared to be evaluated and located by errors.

import {importsOf, rewriteImports} from "./jsonnet.js";

export const MAIN_FILE = "playground.jsonnet";

// length of the snippets accepted as '#code=<base64url>' in the url
export const MAX_ENCODED_SNIPPET = 200000;

// Locations of go-jsonnet are a file and a position, e.g. 'playground.jsonnet:5:8-25' or
// 'playground.jsonnet:(5:8)-(6:13)', the lines and columns starting at 1, the end column being excluded. They are found
// by the extension of the file, followed by the position.
const FILE_EXTENSION = /\.(?:jsonnet|libsonnet):/g;
const POSITION = /(\d+):(\d+)(?:-(\d+))?|\((\d+):(\d+)\)-\((\d+):(\d+)\)/y;
// the characters that end the name of a file in an error message
const FILE_NAME_END = /[\s:()<>]/;
// a file of a default configuration imported by the configuration of an organization, e.g.
// 'vendor/custom/nested/otterdog-defaults.libsonnet'. Capture the basename even
// when the source repository stores its libraries in subdirectories.
const VENDOR_FILE = /^vendor\/[^/]+\/(?:[^/]+\/)*([^/]+)$/;

export const baseName = (path) => path.split("/").pop();

export function encodeSnippet(code) {
  const bytes = new TextEncoder().encode(code);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCodePoint(...bytes.subarray(index, index + 0x8000));
  }
  // without the padding, which only ends the encoded text
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
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

// Shared snippet URLs may refer to another project's vendor directory. Keep
// imports that exist here; adapt missing vendor imports to the available files.
// templateFiles contains browser filenames; defaultConfig is the selected
// template's filename. Add its import when the snippet contains no import.
export function normalizeSnippet(code, templateFiles, defaultConfig) {
  code = rewriteImports(code, ({path}) => {
    if (templateFiles.includes(path)) {
      return path;
    }
    const name = VENDOR_FILE.exec(path)?.[1];
    if (name === undefined) {
      return path;
    }
    // Shared snippets prefer libraries beside the selected template when names collide.
    const sibling = defaultConfig.slice(0, defaultConfig.lastIndexOf("/") + 1) + name;
    if (templateFiles.includes(sibling)) {
      return sibling;
    }
    // Some templates reuse a helper from another directory instead of having
    // their own. Keep the original import if no matching library is available.
    const availableLibrary = templateFiles.find((file) => file.endsWith("/" + name));
    return availableLibrary ?? path;
  });

  if (!importsOf(code).some(({keyword}) => keyword === "import")) {
    code = "local orgs = import '" + defaultConfig + "';\n\n" + code;
  }
  // without trailing empty lines, the content of the editor being compared to it
  return code.trimEnd();
}

// The importer of libjsonnet.wasm creates new contents each time a file is imported, so the evaluation crashes
// when a path is imported again ("a different instance of Contents returned when importing ... again"), e.g. a
// configuration importing its default configuration twice. Each further import of a path therefore gets a distinct
// but equivalent spelling, e.g. 'a.libsonnet' then './a.libsonnet', in the files {filename: content} that are
// evaluated.
export function distinctImports(files, mainFile) {
  const counts = new Map();
  const rewrite = (code) => rewriteImports(code, ({path}) => {
    // './a.libsonnet' being the same file as 'a.libsonnet', its spellings are counted together
    const file = path.replace(/^(?:\.\/)+/, "");
    const count = counts.get(file) ?? 0;
    counts.set(file, count + 1);
    return "./".repeat(count) + file;
  });

  const result = {[mainFile]: rewrite(files[mainFile])};
  for (const [name, content] of Object.entries(files)) {
    if (name !== mainFile) {
      result[name] = rewrite(content);
    }
  }
  return result;
}

// Returns the locations of an error message: {file, from, to, index, text}, the positions being the ones of CodeMirror.
export function errorLocations(message) {
  const locations = [];
  for (const extension of message.matchAll(FILE_EXTENSION)) {
    const end = extension.index + extension[0].length;
    let start = extension.index;
    while (start > 0 && !FILE_NAME_END.test(message[start - 1])) {
      start--;
    }
    POSITION.lastIndex = end;
    const position = POSITION.exec(message);
    if (start < extension.index && position !== null) {
      locations.push({
        // further imports of a path are spelled './<path>', '././<path>', ... (see distinctImports)
        file: message.slice(start, end - 1).replace(/^(\.\/)+/, ""),
        ...rangeOf(position),
        index: start,
        text: message.slice(start, POSITION.lastIndex),
      });
    }
  }
  return locations;
}

const position = (line, column) => ({line: line - 1, ch: column - 1});

function rangeOf([, line, column, endColumn, fromLine, fromColumn, toLine, toColumn]) {
  if (line === undefined) {
    return {from: position(fromLine, fromColumn), to: position(toLine, toColumn)};
  }
  // a column without end is a range of one character
  return {from: position(line, column), to: position(line, endColumn ?? +column + 1)};
}
