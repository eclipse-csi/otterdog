// Evaluates jsonnet snippets with go-jsonnet compiled to WebAssembly (libjsonnet.wasm) outside the main thread,
// so that the playground stays responsive while large configurations are evaluated.
//
// The messages are {id, filename, files}, each answered by {id, json} or {id, error}.

// the runtime of go and go-jsonnet compiled to WebAssembly, vendored with the assets, the build emitting them with the
// hash of their content in their name
const WASM_EXEC = new URL("../../../assets/third_party/js/wasm_exec.js", import.meta.url);
const LIBJSONNET = new URL("../../../assets/third_party/js/libjsonnet.wasm", import.meta.url);

const evaluateSnippet = load();

async function load() {
  importScripts(WASM_EXEC.href);

  const go = new Go();
  const result = await WebAssembly.instantiateStreaming(fetch(LIBJSONNET), go.importObject);
  go.run(result.instance);
  return globalThis.jsonnet_evaluate_snippet;
}

// The importer of libjsonnet.wasm creates new contents each time a file is imported, so the evaluation crashes
// when a path is imported again ("a different instance of Contents returned when importing ... again"), e.g. a
// configuration importing its default configuration twice. Each further import of a path therefore gets a distinct
// but equivalent spelling, e.g. 'a.libsonnet' then './a.libsonnet', in the files that are evaluated.
function distinctImports(files, mainFile) {
  const counts = new Map();
  const rewrite = (code) => code.replace(
    /\b(importstr|importbin|import)(\s*)(?:'([^'\n]*)'|"([^"\n]*)")/g,
    (statement, keyword, space, single, double) => {
      const path = single !== undefined ? single : double;
      const quote = single !== undefined ? "'" : '"';
      const count = counts.get(path) || 0;
      counts.set(path, count + 1);
      return keyword + space + quote + "./".repeat(count) + path + quote;
    }
  );

  const result = {[mainFile]: rewrite(files[mainFile])};
  for (const [name, content] of Object.entries(files)) {
    if (name !== mainFile) {
      result[name] = rewrite(content);
    }
  }
  return result;
}

self.onmessage = async (event) => {
  const message = event.data;
  try {
    const evaluate = await evaluateSnippet;
    const files = distinctImports(message.files, message.filename);
    const json = await evaluate(message.filename, files[message.filename], files, {}, {}, {}, {});
    self.postMessage({id: message.id, json});
  } catch (e) {
    self.postMessage({id: message.id, error: e instanceof Error ? e.message : String(e)});
  }
};
