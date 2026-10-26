// Evaluates jsonnet snippets with go-jsonnet compiled to WebAssembly (libjsonnet.wasm) outside the main thread,
// so that the playground stays responsive while large configurations are evaluated.
//
// The messages are {id, filename, files}, each answered by {id, json} or {id, error, failed}, failed telling that the
// evaluator itself failed, e.g. it could not be loaded or go-jsonnet stopped without memory left, rather than the
// evaluation of the snippet.

import {distinctImports} from "./snippets.js";

// the runtime of go and go-jsonnet compiled to WebAssembly, vendored with the assets, the build emitting them with the
// hash of their content in their name
const WASM_EXEC = new URL("../../../assets/third_party/js/wasm_exec.js", import.meta.url);
const LIBJSONNET = new URL("../../../assets/third_party/js/libjsonnet.wasm", import.meta.url);

let go = null;
const evaluateSnippet = load();

async function load() {
  importScripts(WASM_EXEC.href);

  go = new Go();
  const result = await WebAssembly.instantiateStreaming(fetch(LIBJSONNET), go.importObject);
  go.run(result.instance);
  return globalThis.jsonnet_evaluate_snippet;
}

self.onmessage = async (event) => {
  self.postMessage(await evaluation(event.data));
};

async function evaluation({id, filename, files}) {
  let evaluate;
  try {
    evaluate = await evaluateSnippet;
  } catch (e) {
    return {id, error: "the evaluator could not be loaded: " + messageOf(e), failed: true};
  }

  try {
    const distinct = distinctImports(files, filename);
    return {id, json: await evaluate(filename, distinct[filename], distinct, {}, {}, {}, {})};
  } catch (e) {
    // go-jsonnet stops once its program fails, e.g. without memory left, not once a snippet fails
    return {id, error: messageOf(e), failed: go.exited};
  }
}

const messageOf = (e) => (e instanceof Error ? e.message : String(e));
