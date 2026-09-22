---
description: |
  Triages otterdog issues: classification, duplicate detection, type/priority
  labels, and a summary comment for maintainers. Runs on new issues, on demand
  for a specific existing issue, and weekly over the untriaged backlog.

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
    query: "is:issue is:open label:!bug,enhancement,question,task,needs-triage"
    min: 1
  reaction: eyes

concurrency:
  job-discriminator: ${{ github.event.inputs.issue_number || github.event.issue.number || github.run_id }}

permissions:
  contents: read
  issues: read
  copilot-requests: write

tools:
  github:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    toolsets: [issues]

safe-outputs:
  add-labels:
    allowed:
      - bug
      - enhancement
      - question
      - duplicate
      - invalid
      - documentation
      - help wanted
      - good first issue
      - task
      - python
      - javascript
      - github_actions
      - dependencies
      - priority/p0
      - priority/p1
      - priority/p2
      - needs-triage
    max: 3
  remove-labels:
    allowed:
      - bug
      - enhancement
      - question
      - task
      - needs-triage
      - priority/p0
      - priority/p1
      - priority/p2
    max: 2
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
  issues that are still unlabeled or only carry `needs-triage`, then process each one in turn.

For each issue to triage:
1. Read the title/body, and the repo's available labels.
2. Search for similar/recent issues to detect a duplicate.
3. Classify the type (bug/enhancement/question/task) and set a priority
   (`priority/p0` security or crash / `priority/p1` significant / `priority/p2` minor)
   only when the impact is reasonably clear from the description.
4. Apply at most 2 type/domain labels (plus `documentation`, `python`, `javascript`,
   `github_actions`, `dependencies` when the affected technical area is identifiable).
5. If the issue is clearly a duplicate, apply `duplicate` and cite the original issue number(s).
6. If you cannot classify the issue with reasonable confidence, do not guess: apply only
   `needs-triage` instead of a type label, and say so in your comment. Never apply a type or
   priority label you are not confident about.
7. If the issue was previously mislabeled (e.g. carries a type label that no longer fits, or a
   stale `needs-triage` once you can now classify it), remove the incorrect label(s) via
   `remove-labels` before adding the correct ones.
8. If you encounter an existing comment on the issue that is clearly spam, abuse, or off-topic,
   hide it with the appropriate reason instead of leaving it visible.
9. Post a short comment per issue: summary, label(s) applied/removed, and potential duplicates
   if any. Skip the comment for the weekly sweep if nothing changed for that issue.
