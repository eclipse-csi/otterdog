---
description: |
  Triages otterdog issues: classification, severity/priority/effort estimation,
  duplicate detection, and a summary comment (feasibility, impact, next steps)
  for maintainers. Runs on new issues, on demand for a specific existing issue,
  and weekly over the untriaged backlog.

on:
  issues:
    types: [opened, reopened]
  workflow_dispatch:
    inputs:
      issue_number:
        description: 'Existing issue number to triage'
        required: true
        type: string
  schedule: weekly
  skip-if-no-match:
    query: "is:issue is:open -label:\"ai-triaged\""
    min: 1
  reaction: eyes

concurrency:
  job-discriminator: ${{ github.event.inputs.issue_number || github.event.issue.number || github.run_id }}

permissions:
  contents: read
  issues: read
  copilot-requests: write

tools:
  bash: ["cat", "ls", "find", "grep", "head", "tail", "wc", "gh"]
  github:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    toolsets: [issues]
    min-integrity: none

safe-outputs:
  add-labels:
    allowed:
      - duplicate
      - invalid
      - good first issue
      - help wanted
      - ai-triaged
      - severity:critical
      - severity:high
      - severity:medium
      - severity:low
      - priority:p0
      - priority:p1
      - priority:p2
      - priority:p3
      - type:bug
      - type:feature
      - type:enhancement
      - type:documentation
      - type:question
      - type:task
      - component:configuration
      - component:github-api
      - component:cli
      - component:dashboard
      - component:security
      - component:secrets
      - component:automation
      - effort:small
      - effort:medium
      - effort:large
      - status:needs-triage
      - status:needs-info
      - status:blocked
    max: 7
  remove-labels:
    allowed:
      - duplicate
      - severity:critical
      - severity:high
      - severity:medium
      - severity:low
      - priority:p0
      - priority:p1
      - priority:p2
      - priority:p3
      - type:bug
      - type:feature
      - type:enhancement
      - type:documentation
      - type:question
      - type:task
      - component:configuration
      - component:github-api
      - component:cli
      - component:dashboard
      - component:security
      - component:secrets
      - component:automation
      - effort:small
      - effort:medium
      - effort:large
      - status:needs-triage
      - status:needs-info
      - status:blocked
    max: 6
  add-comment:
    max: 1
  hide-comment:
    max: 3

engine: copilot

timeout-minutes: 10
---

Determine which issue(s) to analyze based on how this run was triggered:
- `workflow_dispatch`: the issue is number `${{ github.event.inputs.issue_number }}`.
- `issues` event (opened/reopened): the issue is the one in the event payload.
- `schedule` (weekly backlog sweep): use the `github` tool's `list_issues`/search to find open
  issues that don't carry the `ai-triaged` label yet, then process each one in turn. This
  includes issues never touched by this workflow and issues previously left at
  `status:needs-triage`/`status:needs-info` (a maintainer removing `ai-triaged` from an issue is
  also how they force a re-triage on demand).

For each issue to triage, apply labels across these independent dimensions — only when you have
reasonable confidence, never guess:

1. **Type** (exactly one): `type:bug`, `type:feature` (brand new capability),
   `type:enhancement` (improves something existing), `type:documentation`, `type:question`,
   or `type:task`.
2. **Component** (one or two, from `otterdog/webapp/*` = `component:dashboard`/`component:automation`
   for webhook handling, `otterdog` CLI code = `component:cli`, jsonnet/otterdog.json model =
   `component:configuration`, GitHub API/provider layer = `component:github-api`, anything touching
   auth/tokens/credentials = `component:security` and/or `component:secrets`).
3. **Severity** (bugs only, exactly one): `severity:critical` (crash, data loss, security),
   `severity:high` (major function broken, no workaround), `severity:medium` (impaired, workaround
   exists), `severity:low` (cosmetic/minor).
4. **Priority** (exactly one): `priority:p0` (drop everything) .. `priority:p3` (nice to have) —
   derive from severity + how many users are likely affected, not from severity alone.
5. **Effort** (exactly one, your best estimate of the fix/implementation size): `effort:small`
   (single well-scoped change), `effort:medium` (touches a few files/areas), `effort:large`
   (design decisions or multi-file/cross-component work).
6. **Duplicate**: if clearly a duplicate, apply `duplicate` and cite the original issue number(s);
   skip severity/priority/effort classification in that case.
7. If you cannot classify type/component with reasonable confidence, or the report is missing
   information needed to assess severity/effort, do not guess: apply `status:needs-triage` (unclear
   overall) or `status:needs-info` (specific missing info — state exactly what's missing) instead
   of forcing a full classification. Do **not** apply `ai-triaged` in this case, so the issue stays
   eligible for the next weekly sweep once more information is available.
8. Once you reach a confident classification (a `type:*` label applied, or `duplicate`), also
   apply `ai-triaged` to mark the issue as processed — this is what keeps it out of future sweeps.
9. If the issue was previously mislabeled (stale type/severity/priority/effort, or a
   `status:needs-triage`/`status:needs-info` that no longer applies now that you can classify it),
   remove the incorrect label(s) via `remove-labels` before adding the correct ones. Leave
   `ai-triaged` alone either way — only a maintainer removing it manually should trigger a
   from-scratch re-triage.
10. If you encounter an existing comment that is clearly spam, abuse, or off-topic, hide it with
    the appropriate reason instead of leaving it visible.

Post one short comment per issue containing:

- **Summary**: one sentence summarizing the reported problem or request.
- **Label changes**: list each label applied or removed, with a brief reason. Do not restate
  the issue.
- **Feasibility & impact**: assess each item below based only on information available from the
  issue and repository. If there is not enough evidence to make a reliable assessment, write
  `unclear` rather than guessing.
  - **Code**: likely affected module(s), file(s), or subsystem. Keep this to the most relevant
    areas rather than providing an exhaustive file list.
  - **Config / organizations**: indicate whether the change affects the `otterdog.json`/Jsonnet
    configuration model or schema, or changes behavior for GitHub organizations already managed
    by otterdog. State whether existing deployments would require a configuration change, an
    `otterdog apply` re-run, or neither.
  - **Deployment**: indicate whether this is a CLI-only change or whether it also requires
    changes to the webapp/dashboard, database schema or migration, webhook handling, bot
    synchronization, or another deployed component.
  - **Breaking change**: `yes`, `no`, or `unclear`. If yes, briefly state what breaks and who is
    affected, such as CLI users, webapp deployments, or existing `otterdog.json`/Jsonnet
    configurations. Phrase the explanation so it can be reused in the PR template's "Breaking
    change details" section.
  - **GitHub plan dependency**: state whether the behavior depends on GitHub Free, Team, or
    Enterprise Cloud features, such as rulesets, branch protections, or custom roles. Identify
    the relevant plan(s), or write `none known` if the behavior is plan-independent.
  - **Coding-agent suitability**: state either `ready for implementation` or `maintainer decision
    required`. If a maintainer decision is required, briefly identify the unresolved design or
    product decision.
- **Potential duplicates**: list possible duplicate or closely related issues using issue
  numbers. If none are found, write `none found`.

Keep each item above to one short factual line — no multi-sentence explanations. The comment as a
whole will typically run to around 10 lines given the number of items; do not pad it beyond that,
and combine the summary/label-changes/duplicates items onto a single line each even when there are
several labels or duplicates to list. Do not invent implementation details, affected files,
compatibility constraints, GitHub plan requirements, or duplicate relationships that cannot be
supported by the available information.

Skip the comment for the weekly sweep if nothing changed for that issue.