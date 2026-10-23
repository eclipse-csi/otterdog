import {MAIN_FILE} from "./snippets.js";

// Evaluates the files of the playground in a worker, see jsonnet-worker.js. Returns a function evaluating the files
// {filename: content} to the json of the main file.
export function createEvaluator() {
  const worker = new Worker(new URL("./jsonnet-worker.js", import.meta.url));

  const pending = new Map();
  let nextId = 0;

  worker.onmessage = (event) => {
    const {id, json, error} = event.data;
    const {resolve, reject} = pending.get(id);
    pending.delete(id);
    if (error === undefined) {
      resolve(json);
    } else {
      reject(new Error(error));
    }
  };
  worker.onerror = (event) => {
    for (const {reject} of pending.values()) {
      reject(new Error("the evaluator failed: " + event.message));
    }
    pending.clear();
  };

  return (files) => new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, {resolve, reject});
    worker.postMessage({id, filename: MAIN_FILE, files});
  });
}

// Evaluates the shown document once its content has not changed for a while, only its latest content being evaluated
// after an evaluation that took longer. A document keeps its last evaluation, {code, value, duration} or
// {code, error}, as long as its content does not change.
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

    const document = current();
    const code = document.doc.getValue();
    if (document.result?.code !== code) {
      running = true;
      evaluating();
      document.result = await evaluationOf(evaluate, code);
      running = false;
      evaluated(document);
    }

    if (rerun) {
      rerun = false;
      await run();
    } else if (document === current()) {
      show(document);
    }
  }

  return (delay) => {
    clearTimeout(timer);
    timer = setTimeout(run, delay);
  };
}

async function evaluationOf(evaluate, code) {
  const start = performance.now();
  try {
    return {code, value: JSON.parse(await evaluate(code)), duration: performance.now() - start};
  } catch (e) {
    return {code, error: e.message};
  }
}
