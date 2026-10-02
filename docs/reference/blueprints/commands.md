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
