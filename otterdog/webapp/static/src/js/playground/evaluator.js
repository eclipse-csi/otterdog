import {MAIN_FILE} from "./snippets.js";

// The error of an evaluation that failed because of the evaluator, e.g. without memory left, rather than because of
// the evaluated files.
export class EvaluatorError extends Error {}

// Evaluates the files of the playground in a worker, see jsonnet-worker.js. Returns a function evaluating the files
// {filename: content} to the json of the main file. A worker that failed is replaced by a new one for the next
// evaluations, the pending ones failing with an EvaluatorError.
export function createEvaluator() {
  const pending = new Map();
  let worker = null;
  let nextId = 0;

  function start() {
    worker = new Worker(new URL("./jsonnet-worker.js", import.meta.url));
    worker.onmessage = (event) => settle(event.data);
    worker.onerror = (event) => fail("the evaluator failed: " + event.message);
  }

  function settle({id, json, error, failed}) {
    const {resolve, reject} = pending.get(id);
    pending.delete(id);
    if (failed) {
      reject(new EvaluatorError(error));
      fail(error);
    } else if (error === undefined) {
      resolve(json);
    } else {
      reject(new Error(error));
    }
  }

  function fail(message) {
    worker.terminate();
    worker = null;
    for (const {reject} of pending.values()) {
      reject(new EvaluatorError(message));
    }
    pending.clear();
  }

  return (files) => new Promise((resolve, reject) => {
    if (worker === null) {
      start();
    }
    const id = nextId++;
    pending.set(id, {resolve, reject});
    worker.postMessage({id, filename: MAIN_FILE, files});
  });
}

// the files evaluated for a code with the files {filename, content} of a default configuration
export function filesOf(code, templateFiles) {
  return Object.fromEntries([[MAIN_FILE, code], ...templateFiles.map((file) => [file.filename, file.content])]);
}

// Evaluates the shown document once its content has not changed for a while, only its latest content being evaluated
// after an evaluation that took longer. A document keeps its last evaluation, see evaluationOf, as long as its content
// does not change.
//
// Returns a function scheduling the evaluation after a delay, the callbacks being notified when an evaluation starts,
// when a document has been evaluated, and when the evaluation of the shown document is to be shown.
export function createScheduler(evaluate, {current, evaluating, evaluated, show}) {
  let timer = null;
  let running = false;
  let rerun = false;

  async function run() {
    if (running) {
      rerun = true;
      return;
    }

    const d = current();
    const code = d.code;
    if (d.result?.code !== code) {
      running = true;
      evaluating();
      d.result = await evaluationOf(evaluate, code);
      running = false;
      evaluated(d);
    }

    if (rerun) {
      rerun = false;
      await run();
    } else if (d === current()) {
      show(d);
    }
  }

  return (delay) => {
    clearTimeout(timer);
    timer = setTimeout(run, delay);
  };
}

// the evaluation of a code: {code, value, duration}, or {code, error, failed}, failed telling that the evaluator failed
export async function evaluationOf(evaluate, code) {
  const start = performance.now();
  try {
    return {code, value: JSON.parse(await evaluate(code)), duration: performance.now() - start};
  } catch (e) {
    return {code, error: e.message, failed: e instanceof EvaluatorError};
  }
}
