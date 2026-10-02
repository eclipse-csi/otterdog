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
