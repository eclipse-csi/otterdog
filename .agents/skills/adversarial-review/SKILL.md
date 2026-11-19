---
name: adversarial-review
description: Review the changes of an otterdog branch adversarially before a pull request is opened. Try to disprove the assumptions of the change, verify each finding on the state reviewed, and give a verdict (ready, blocked or inconclusive). Read-only by default; confirmed bugs are fixed only when the user asks for a fix pass. Use it before opening or preparing a pull request, and when asked for a self-review, a pre-PR review or a critical review of the current changes. Nothing is posted to GitHub.
---

# Adversarial review before a pull request

The conventions, commands, git rules and GitHub safety rules are in `AGENTS.md`. This review posts nothing to GitHub
and does not replace the review of a maintainer. It ends with a verdict, and a pull request is not opened while the
verdict is `blocked`.

## Ground rules

- **Try to disprove the assumptions of the change.** For everything the change takes for granted (a value GitHub
  always returns, an order, a GitHub plan, a permission, a single caller), look for the input, the organization or
  the sequence of commands where it does not hold. Zero findings is a valid outcome: do not manufacture any.
- **Read-only by default.** The review changes no file of the checkout. Fix the confirmed bugs only when the user asks
  for a fix pass (step 5). A `blocked` verdict stands even if the review changed nothing.
- **Checks that do not fix.** `prek` rewrites files (`ruff check --fix`, `ruff format`, the whitespace and
  end-of-file fixers). During the review, run it in a separate temporary worktree checked out at `HEAD`, not in the
  one of question 8, which holds `<base>`. The worktree has no virtual environment of its own and the hooks call
  `poetry run`, so activate the one of the checkout first:
  `cd <tmp-dir> && . <checkout>/.venv/bin/activate && prek run --files <files>`. A worktree at `HEAD` leaves out
  uncommitted changes: check those with the non-fixing commands on the checkout, `poetry run ruff check --no-fix
  <files>`, `poetry run ruff format --check <files>`, and `pytest`. If a check rewrote a file anyway, report it
  rather than keep the change.
- **Review with fresh eyes.** If your tool can run a separate agent or session, give it the diff, the goal of the
  change and this skill, but not your own analysis, so that it does not inherit your assumptions. Otherwise, re-read
  the diff from the start, file by file, as if someone else had written it.
- **No finding without evidence.** Keep a finding only with a concrete failure scenario (input or state, then wrong
  result) checked on the state you reviewed (step 1), or better, reproduced by a test.
- **Never write to GitHub.** Scenarios such as `apply` then `plan` are checked with a simulated provider, never
  against a real organization.

## 1. Define the state under review

`<base>` is the branch the pull request will target, usually `main` of `eclipse-csi/otterdog`, kept up to date.

```shell
git status --short                         # staged, unstaged and untracked files
git diff <base>...HEAD --stat              # the commits of the branch: what the pull request will contain
git diff <base>...HEAD
git diff HEAD                              # local changes to tracked files
git ls-files --others --exclude-standard   # untracked files, which no git diff shows
```

- Keep the branch diff and the local changes apart. If the worktree is not clean, include a local change only if it
  will be committed with the pull request; when that is unclear, ask the user.
- Read the untracked files that are part of the change.
- Read the issue or the request, to know what the change must do. Then read in full the files the change touches, the
  callers of every changed function, the other models that follow the same pattern, and the tests that cover them.

## 2. Attack the change

Answer each question that applies to the files touched. A "no" or an "I don't know" is a lead to verify, not a
finding.

1. **Is `plan` empty right after `apply`?** Otterdog is stateless: `apply` recomputes the diff, so nothing may rely
   on an earlier `plan`. A value that the configuration and the live state normalise differently (order, case,
   default, `None`, empty value, `UNSET`) shows up as a change on every run. Check it with a simulated provider: the
   HTTP mock of the integration tests (fixture `github` in `tests/providers/github/integration/conftest.py`) or the
   fixtures of `tests/models/`. The live state that GitHub returns after the apply must give no patch against the
   configuration. Check also that the patch sends only the changed fields, through the right provider (REST, GraphQL
   or web UI), and what happens when the resource is created, renamed or deleted, and with `--delete-resources`.
2. **Does a rerun converge after a partial apply?** If `apply` updates the first resource and fails on the second,
   the next `apply` must send only what is still missing: no new modification of the resource already updated, and
   no duplicate creation. Check it with the HTTP mock: an error response for the second resource, then a second diff
   from the live state the first run left. A test of idempotence after a fully successful apply does not cover this.
   The same applies when the response of a write is lost (5xx, connection error): the write may have been applied
   although otterdog reports a failure, and the REST requester sends a `PUT` or `DELETE` again, whose repetition
   may get another answer, e.g. a 404 for a deletion already applied (see the Provider section of
   `github-config-property`).
3. **What does the provider do when GitHub does not return the value?** A field that is inaccessible (GitHub plan,
   403, 404), a value that is really empty, and an incomplete response (a failed page of a paginated list, a 500) are
   different cases that may need different handling. Check that the code tells them apart, and above all that
   otterdog never turns an incomplete read into a request to create, modify or delete something. `UNSET` suits an
   optional field whose unavailability is established; an inventory whose read is incomplete must stop the
   computation of the patch for that scope.
   `tests/providers/github/integration/test_secret_read_failures.py` shows the expected behaviour for secrets: a
   failed read aborts, and an empty answer confirmed by GitHub is valid.
4. **Do all the homes of a setting agree?** The model and its metadata flags, `validate()`, the default template,
   the JSON schema, the `provider` in `settings.json`, the reference docs and the Playground catalogs. The
   `github-config-property` skill lists them. One forgotten home is the most common bug.
5. **Does every existing configuration still validate and give the same plan?** A changed default, a renamed key or
   a new required key is a breaking change, whose migration path goes in the description of the pull request (see
   the `pr-description` skill). The code must run on Python 3.11 to 3.14.
6. **What happens when it fails?** Expected failures are reported with context and a non-zero exit code, without a
   traceback. An unexpected status, such as an undocumented 422, fails explicitly, on reads and writes alike, instead
   of becoming `UNSET` or a silent success. Check whether one failing resource or organization stops the others when
   it should not.
7. **Can outside input reach it?** In the webapp, webhook payloads, `/otterdog` comments, Playground input and the
   content of configuration repositories come from outside: check how they are validated before they reach Jsonnet,
   file paths, queries or GitHub calls. Tokens and credentials must not reach logs, output or error messages. In
   `.github/workflows/`, check the `${{ }}` expressions used in `run:` steps and the job permissions.
8. **Does each new test fail without the change, for the expected reason?** Run it against the old implementation in
   an isolated environment that leaves the shared checkout untouched, for example a temporary worktree. Breaking the
   code by hand instead can make the test fail for another reason.

    ```shell
    git worktree add --detach <tmp-dir> <base>                # outside the checkout
    cp <new test files and fixtures> <tmp-dir>/<same paths>
    cd <tmp-dir> && <checkout>/.venv/bin/python -m pytest <test files>
    git worktree remove --force <tmp-dir>
    ```

    The virtual environment of the checkout is reused: pytest imports `otterdog` from the current directory
    (`pythonpath` in `pyproject.toml`), so the old code is tested. The test must fail on the assertion that targets
    the regression, not on an import error or a missing fixture. When it cannot run against the old code, say
    exactly why in the report.
    Check also that the tests cover the cases above, not only the expected path, and never access GitHub.

9. **Does the documentation describe the code as it is now?** Examples, reference tables and validation rules.
10. **Does the branch hold only this change?** No unrelated changes, debug leftovers, generated files edited by
    hand, or local files that must never be committed (`otterdog.json`, `.env`, `*.pem`, `values*.yaml`, `orgs/`).

## 3. Classify the findings

- **Confirmed**: traced through the code or reproduced by a test, on the state reviewed.
- **Open hypothesis**: credible but not reproduced. Say what is missing to settle it.
- **Dismissed**: the lead did not hold.

## 4. Verdict and report

The verdict comes first, with its reason:

- **`ready`**: no confirmed finding against the change, and the checks it needs ran and passed.
- **`blocked`**: at least one confirmed bug, or a required check fails. The pull request is not opened until it is
  fixed.
- **`inconclusive`**: a point that decides could not be settled (a check could not run, a scenario could not be
  reproduced, the scope is unclear). Say what is missing, and let the user decide.

Then:

- the state reviewed: the commit, and the local changes included;
- the confirmed findings, first: `file:line`, failure scenario, evidence (test or trace), and whether the finding
  concerns only local changes;
- the open hypotheses, only if they change the decision to open the pull request;
- the dismissed leads only when their explanation helps the reviewer of the pull request;
- the checks that ran and their results, and the checks that were skipped, with the reason;
- the points for the "Notes for reviewers" section of the pull request: the risky areas, the open hypotheses, and
  what was not tested (for example no live test, or which GitHub plan was used). The `pr-description` skill writes
  them into the description.

## 5. Fix pass, on request

When the user asks for the confirmed bugs to be fixed:

1. Fix them with the skill that matches the code, and add a regression test for each one, checked as in question 8.
2. Leave design and behaviour choices to the user: describe the options instead of choosing one silently.
3. Run the checks of `AGENTS.md` again for the files touched, review the new diff, and give a new verdict.

Commit, push or open the pull request only when the user asks.
