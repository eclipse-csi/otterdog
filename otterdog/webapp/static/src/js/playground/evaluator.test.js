import assert from "node:assert/strict";
import {test} from "node:test";

import {EvaluatorError, createEvaluator, evaluationOf} from "./evaluator.js";

// workers answering the evaluations with the given answers, by evaluation
class FakeWorker {
  static created = [];
  static answers = [];

  constructor() {
    this.terminated = false;
    FakeWorker.created.push(this);
  }

  postMessage(message) {
    const answer = FakeWorker.answers.shift();
    setTimeout(() => (answer === "crash" ? this.onerror({message: "crash"}) : this.onmessage({data: {id: message.id, ...answer}})));
  }

  terminate() {
    this.terminated = true;
  }
}

globalThis.Worker = FakeWorker;

test("errors of the evaluator are told apart from errors of the evaluated files", async () => {
  FakeWorker.created = [];
  FakeWorker.answers = [{json: "{}"}, {error: "playground.jsonnet:1:1 Unknown variable"}, {error: "Go program has already exited", failed: true}];
  const evaluate = createEvaluator();

  assert.equal(await evaluate({}), "{}");
  const error = await evaluate({}).catch((e) => e);
  assert.ok(!(error instanceof EvaluatorError) && error.message.includes("Unknown variable"));
  await assert.rejects(evaluate({}), EvaluatorError);
  assert.equal(FakeWorker.created.length, 1);
  assert.ok(FakeWorker.created[0].terminated, "a failed worker is terminated");
});

test("a failed worker is replaced for the next evaluations", async () => {
  FakeWorker.created = [];
  FakeWorker.answers = ["crash", {json: "{\"a\": 1}"}];
  const evaluate = createEvaluator();

  const failed = await evaluationOf(() => evaluate({}), "code");
  assert.deepEqual(failed, {code: "code", error: "the evaluator failed: crash", failed: true});
  assert.equal(await evaluate({}), "{\"a\": 1}");
  assert.equal(FakeWorker.created.length, 2);
});
