---
name: pr-description
description: Write the description of an otterdog pull request from the template .github/pull_request_template.md, as a draft, for the exact diff reviewers will see. Fill each section from evidence (the diff, the checks that ran on it, the verdict of the adversarial review that covers it), classify the type of change and breaking changes with otterdog's criteria, and leave every box unticked until the evidence supports it. Use it when asked to write, prepare or update the description of a PR, or before opening one. Nothing is posted to GitHub unless the user asks.
---

# Write a pull request description

Draft the description for the exact diff reviewers will see. Reuse test results and review findings only when they
still apply to that diff. Leave each checkbox unticked until the evidence supports it.

The conventions, the git rules and the rules on pull requests are in `AGENTS.md`. The description follows
`.github/pull_request_template.md`: read it, since this skill maps its sections but does not copy them.

## Ground rules

- **Only evidence.** Every statement and every ticked box comes from the diff, from a check that ran on that diff,
  or from the user. When you do not know, leave the box unticked or ask.
- **Tested means run.** A request from the user authorizes a live test; only the result of a run that happened
  justifies ticking it. Agents test against GitHub only on explicit request (`AGENTS.md`).
- **A draft.** Write the description in the reply, or in a file the user names. Open or update the pull request
  (`gh pr create --body-file <file>`, `gh pr edit`) only when the user asks.
- **The review gate.** A new pull request needs the verdict of an `adversarial-review` that covers its exact diff:
  reuse a review already done only if it covers that diff, with the same base (see "Reuse" in step 1), otherwise run
  one. For an editorial change to the description of an existing pull request, keep its verdict while it still
  applies. With a `blocked` verdict, the pull request is not opened; you may still draft a description that exposes
  the blocking findings.

## 1. Define the diff and collect the evidence

`<base>` is the branch the pull request targets, usually `main` of `eclipse-csi/otterdog`.

```shell
git rev-parse HEAD
git log --format='%h %s' <base>..HEAD
git diff <base>...HEAD                                       # read it in full, not only --stat
git status --short                                           # local changes are not in the pull request yet
# existing pull request only:
gh pr view <number> -R <owner>/<repo> --json headRefOid,baseRefName
gh pr diff <number> -R <owner>/<repo>
```

- **The target diff.** For a new pull request, it is `git diff <base>...HEAD`. For an existing pull request, it is
  its remote diff (`gh pr diff`), whatever `HEAD` is; compare `headRefOid` with `git rev-parse HEAD` to see whether
  the checkout matches it. Use the local diff instead only when the user explicitly prepares the description of a
  future push, and tell them that the draft becomes true once it is pushed.
- **Uncommitted changes** are not covered by the SHA of `HEAD`. If the draft depends on some of them, list them
  separately.
- **The evidence** for that diff: the issue it addresses (from the user, the branch or the commits; never guessed),
  the checks that ran with their results, the checks that were skipped with the reason, and the review report.
- **Reuse.** Reuse a review verdict only when it covers the exact target diff, with the same base. Reuse a check
  result only when the code, configuration and dependencies relevant to that check are unchanged, shared code
  included: a provider test depends on `rest/requester.py` as much as on its client. Otherwise, rerun the check or
  report it as unverified for this draft.

## 2. Fill the sections

Keep the headings of the template, in its order. The HTML comments of the template can be removed.

- **Description**: what the change does and why, for a reviewer who has not seen the conversation. Start with the
  effect users see (CLI, configuration, webapp, bot), then the internals. Describe the final state of the branch,
  not how you got there.
- **Related issue**: `Fixes #<n>` when the change closes the issue, `Relates to #<n>` otherwise. Without a known
  issue, remove the line rather than leave `Fixes #`.
- **Type of change**: tick what applies. A change is **breaking** when existing users must act, or get a different
  result without changing anything:
    - a changed default in `otterdog-defaults.libsonnet`, which changes the next `plan` of every organization that
      uses the template;
    - a renamed, removed or newly required key of the configuration or of a schema;
    - a new resource type whose omission plans removals of live items (see `github-resource-type`);
    - a changed command, option, output format or exit code that scripts may rely on;
    - a change that webapp deployments must act on (configuration, database, permissions of the GitHub App).
- **Breaking change details**: what breaks, who is affected (CLI users, webapp deployments, existing
  configurations), and the migration path. Remove the section for a change that is not breaking. Committers update
  `CHANGELOG.md` at release time (`AGENTS.md`): edit it only if the user asks.
- **Tests**: keep this section in every case.
    - Tick "Unit tests added / updated" and list the test files, or tick "No test added" and say why (documentation
      only, agent instructions).
    - Under "Manual testing", tick "GitHub API calls only stubbed / mocked" only when tests that exercise mocked
      GitHub calls ran on this diff, and no live test did. Leave it unticked for a change without GitHub calls.
      Tick "Tested on a real GitHub organization" only with the result of a live run, and with the organization,
      the GitHub plan and the commands that ran.
    - List the checks that ran (`prek`, the `pytest` targets, `make docs`, `npm test`) and the checks that were
      skipped, with the reason.
- **How to reproduce / test scenario**: steps a reviewer can follow. Prefer the tests that reproduce the behaviour.
  A step that needs a live organization says so, names the GitHub plan it needs, and uses a test organization.
- **Screenshots**: required when the change affects the web app UI, or the messages and checks of the bot on pull
  requests. Ask the user for them, or keep the section with a note that they are missing. Remove it otherwise.
- **Checklist**: each item mixes a change and a check; report both against the actual wording of the template.
    - "Documentation updated (... `make docs` builds)": tick it when `docs/` was updated as the change needs and
      `make docs` passed on this diff. If the docs changed but `make docs` did not run, leave it unticked and say so.
    - "Default template / examples updated if the config schema changed": the template can need a change without a
      schema change (a new or changed default). Tick it when the template and examples were updated as the change
      needs, and say which; leave it unticked with "not applicable" when neither the schema nor the defaults
      changed.
- **Notes for reviewers**: the verdict of `adversarial-review`, the commit it covers and its reason, the open
  hypotheses that matter for the decision, the risky areas, the behaviour that depends on the GitHub plan (Free,
  Team, Enterprise Cloud), what was not tested, and a suggested review order for a large change.

## 3. Check the draft

- Every ticked box matches evidence for this diff, and every section that does not apply is removed, except Tests.
- The draft holds no credentials and nothing from local configuration files (`otterdog.json`, `.env`, `orgs/`). It
  names a real organization only when the user gives it for the description.
- The draft says which commit it describes, and whether it depends on changes that are not pushed yet.

Present the draft to the user, with the open questions (missing issue, screenshots, live test details).
