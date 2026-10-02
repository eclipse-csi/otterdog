# Comment Commands

Blueprints can be driven from GitHub comments, similar to Dependabot. Commands are plain comments starting with
`/otterdog`. Where a command works depends on its scope:

| Scope        | Where the comment is accepted                                                      |
|--------------|------------------------------------------------------------------------------------|
| config repo  | pull requests of the configuration repository (the existing configuration commands) |
| pull request | pull requests of any repository, in particular remediation PRs `otterdog/blueprint/<id>` |
| any          | issues and pull requests of any repository of the organization                     |

Every blueprint command requires **write access** to the repository the comment is made in, including the read-only
`/otterdog status`, as each command costs GitHub API calls on behalf of the organization. Otterdog answers every
command with a comment, also when it fails. Replying on plain issues requires the GitHub App
permission `Issues: Read & Write`, see [installation](../../operating_otterdog/install.md).

## `/otterdog recheck [<blueprint-id>]`

Scope: any. Forces an evaluation, ignoring `BLUEPRINT_CHECK_INTERVAL` and the stored per-repository status.

- In the configuration repository, every repository matched by the blueprint's selector is evaluated.
- In any other repository, only that repository is evaluated.
- Without a blueprint id, all blueprints of the organization are evaluated.

Examples:

```text
/otterdog recheck
/otterdog recheck codeql
```

Otterdog replies with the blueprints and repositories it scheduled. Remediation pull requests are opened or updated
in the background; follow them on the dashboard. A blueprint dismissed for a repository stays dismissed, see
`/otterdog recreate`.

## `/otterdog rebase`

Scope: pull request, on a remediation pull request (branch `otterdog/blueprint/<id>`). Brings the branch up to date
with the default branch and writes the blueprint's current files on top:

- a branch whose commits were all made by otterdog is reset to the default branch, stale commits disappear
- a branch with commits of maintainers gets the default branch merged in, their edits are preserved

```text
/otterdog rebase
```

## `/otterdog recreate`

Scope: pull request, on a remediation pull request, open or closed. Discards the branch, recreates it from the
default branch with the current blueprint content and reuses the pull request, reopening it if it was closed. A
dismissal of the blueprint for this repository is cleared. The resulting diff contains only differences against the
current default branch.

```text
/otterdog recreate
```

## `/otterdog ignore`

Scope: pull request, on a remediation pull request. Dismisses the blueprint for this repository explicitly and closes
the pull request. This is the same state a pull request reaches when it is closed without merging, but the comment
makes the intent visible. `/otterdog recreate` reinstates the blueprint.

```text
/otterdog ignore
```

## `/otterdog status [<blueprint-id>] [--workflow <name>] [--label <label>] [--status <status>]`

Scope: any. Posts one comment, updated in place on repeated runs, with one row per repository the blueprint applies
to: the stored blueprint status, the remediation pull request with its state, mergeability and labels, an
**outdated** marker when the pull request content is older than the current blueprint, and one label per job of the
latest workflow run on the default branch in the form `workflow / job: <status>`.

- In the configuration repository every repository matched by the blueprint's selector is listed, in any other
  repository only that repository.
- Without a blueprint id, every blueprint of the organization is reported.

The status text is GitHub's own value, verbatim: the job's `conclusion` when completed (`success`, `failure`,
`cancelled`, `skipped`, `timed_out`, `action_required`, `neutral`, `stale`), otherwise its `status` (`queued`,
`in_progress`, `waiting`, `pending`, `requested`). A workflow without a run on the default branch shows `no_run`.
Every label links to the job's log.

Which workflows are reported, first match wins:

1. `--workflow <name>` on the command, by file name (with or without extension) or by the workflow's `name`
2. `status_workflow` in the blueprint config, a name or a list
3. the workflows the blueprint itself manages: the scorecard workflow for `scorecard_integration`, the workflows
   among the `files` of a `required_file` blueprint
4. nothing defined: every workflow of the repository, every job

`--label` keeps only repositories whose pull request carries that label, `--status` only repositories with at least
one job in that GitHub status.

Examples:

```text
/otterdog status
/otterdog status codeql
/otterdog status codeql --workflow build.yml
/otterdog status codeql --label blueprint:codeql
/otterdog status codeql --status failure
/otterdog status codeql --workflow build --status in_progress
```

Cost: one pull request, one workflow list, one run list and one job list per workflow for every repository; results
are cached for the duration of one command.
