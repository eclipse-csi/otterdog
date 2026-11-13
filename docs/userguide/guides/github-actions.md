# Securing GitHub Actions

GitHub Actions settings exist on organization level ([`settings.workflows`](../../reference/organization/settings.md#workflow-settings))
and on repository level ([`workflows`](../../reference/organization/repository/index.md#workflow-settings)). When the
organization setting is more restrictive, the repository setting is ignored, see
[Organization settings take precedence](inheritance.md#organization-settings-take-precedence). This guide covers
the settings that limit what workflows can do.

## Restrict the permissions of the GITHUB_TOKEN

Every workflow run receives a `GITHUB_TOKEN`. The setting `default_workflow_permissions` defines its default
permissions:

- `read`: read access to the repository contents and packages only
- `write`: read and write access for all permission scopes

Workflows that need more permissions declare them explicitly with the
[`permissions`](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)
key, e.g. a release job:

``` yaml
jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write # create the release
    steps:
      ...
```

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    workflows+: {
      default_workflow_permissions: "read",
    },
  },
}
```

!!! tip "Recommendation"

    Use `read` as default and grant additional permissions per workflow or job. A compromised step, e.g. a
    dependency of the build, can then not modify the repository. Since February 2023, GitHub uses `read` for new
    organizations, but older organizations and repositories may still use `write`, see the
    [GitHub changelog](https://github.blog/changelog/2023-02-02-github-actions-updating-the-default-github_token-permissions-to-read-only/).
    A configuration imported from such an organization contains `default_workflow_permissions: "write"`.

To switch an existing organization from `write` to `read`:

1. Identify the workflows that need write access, e.g. workflows that push commits or tags, create releases,
   publish packages or comment on pull requests, and add the required `permissions` to them.
2. Switch the repositories with such workflows first, e.g. one repository at a time, with
   `workflows+: { default_workflow_permissions: "read" }`.
3. Switch the organization setting. From then on, a repository setting `write` is ignored.
4. Watch for failing workflow runs with errors like `Resource not accessible by integration`.

## Prevent workflows from approving pull requests

The setting `actions_can_approve_pull_request_reviews` controls whether workflows can create and approve pull
requests with the `GITHUB_TOKEN`.

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    workflows+: {
      actions_can_approve_pull_request_reviews: false,
    },
  },
}
```

!!! info "Organization policy"

    An approval by a workflow is not a human review: disable this setting if pull requests require reviews. Some
    automation, e.g. tools that open release or update pull requests with the `GITHUB_TOKEN`, needs this setting;
    in that case, consider a GitHub App token for this automation instead. GitHub disables the setting by default
    for new organizations, see
    [Preventing GitHub Actions from creating or approving pull requests](https://docs.github.com/en/organizations/managing-organization-settings/disabling-or-limiting-github-actions-for-your-organization#preventing-github-actions-from-creating-or-approving-pull-requests).

## Control which actions can run

The setting `allowed_actions` controls which actions and reusable workflows can run:

- `all`: any action
- `local_only`: only actions and reusable workflows defined in the organization
- `selected`: actions created by GitHub (`allow_github_owned_actions`), by verified creators
  (`allow_verified_creator_actions`) and actions that match `allow_action_patterns`

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    workflows+: {
      allowed_actions: "selected",
      allow_github_owned_actions: true,
      allow_verified_creator_actions: false,
      allow_action_patterns+: [
        "my-org/*",
        "example-owner/example-action@*",
      ],
    },
  },
}
```

!!! info "Organization policy"

    An allow-list reduces the risk of running untrusted code, but every new action requires a configuration
    change. It suits organizations with a central review of dependencies. Otherwise, pinning actions to a
    commit SHA, e.g. with the [Pin Workflow](../../reference/blueprints/pin-workflow.md) blueprint, and keeping them
    up to date with Dependabot provides a good level of control with less maintenance.

Patterns are described in
[Allowing select actions and reusable workflows to run](https://docs.github.com/en/organizations/managing-organization-settings/disabling-or-limiting-github-actions-for-your-organization#allowing-select-actions-and-reusable-workflows-to-run).

## Require actions to be pinned to a commit SHA

A tag or a branch of an action, e.g. `actions/checkout@v4`, can be moved to other code, for example after the
repository of the action has been compromised. A full-length commit SHA cannot. When the setting
`sha_pinning_required` is enabled, a workflow that uses an action that is not pinned to a full-length commit SHA
fails, including the actions of the organization and the actions authored by GitHub. Reusable workflows can still be
referenced by a tag. The setting applies whatever the value of `allowed_actions`.

When the organization requires SHA pinning, the setting of its repositories is ignored. Otherwise, a repository can
require it on its own, e.g. to adopt it one repository at a time:

=== "Organization"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      settings+: {
        workflows+: {
          sha_pinning_required: true,
        },
      },
    }
    ```

=== "Repository"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-repo') {
          workflows+: {
            sha_pinning_required: true,
          },
        },
      ],
    }
    ```

The actions locked in a lockfile, written by `gh actions-lock`, satisfy this setting without changes to the
workflow files, see [Enforce workflow lockfiles](https://docs.github.com/en/actions/how-tos/administer/enforce-workflow-lockfiles).
The **Require lockfile** rule of an actions policy, which blocks the workflows that are not in the lockfile, is not
supported by otterdog yet, see [Control who and what can run workflows](#control-who-and-what-can-run-workflows).

!!! info "Organization policy"

    Pin the actions of the existing workflows before requiring it, otherwise their runs fail. The
    [Pin Workflow](../../reference/blueprints/pin-workflow.md) blueprint opens pull requests that pin the actions
    of the workflows of the repositories, and Dependabot keeps the pinned commits up to date. See
    [Using third-party actions](https://docs.github.com/en/actions/reference/security/secure-use#using-third-party-actions).

## Control who and what can run workflows

Actions policies, called workflow execution protections by GitHub, block the runs of the workflows they target
unless they are allowed, see
[Controlling workflow execution](https://docs.github.com/en/actions/how-tos/administer/control-workflow-execution).
A policy targets workflow files, and on organization level repositories, and requires rules:

| Rule             | Allows                                                                                         |
|------------------|------------------------------------------------------------------------------------------------|
| `allowed_actors` | only these [actors](../../reference/organization/repository/allowed-actor.md) to run the workflows, e.g. `#Maintain` or `@my-org/releng` |
| `allowed_events` | only these events to trigger the workflows, e.g. `push`, `pull_request` or `workflow_dispatch` |

A rule set to `null` is not required. Like rulesets, the policies of the organization and of a repository layer: a
run must be allowed by all the policies that target its workflow.

=== "Organization"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      actions_policies+: [
        orgs.newOrgActionsPolicy('release') {
          include_repo_names: ["~ALL"],
          include_workflows: [".github/workflows/release.yml"],
          allowed_actors: ["#Maintain", "@my-org/releng"],
          allowed_events: ["workflow_dispatch"],
        },
      ],
    }
    ```

=== "Repository"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-repo') {
          actions_policies: [
            orgs.newRepoActionsPolicy('release') {
              include_workflows: [".github/workflows/release.yml"],
              allowed_actors: ["#Maintain"],
            },
          ],
        },
      ],
    }
    ```

The `pull_request_target` event runs a workflow of the base repository with its secrets for pull requests from
forks, which makes it a frequent target of attacks. GitHub blocks it in public repositories that have no applicable
event policy, see
[Securely using pull_request_target](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target).
A workflow that needs it, e.g. to label pull requests, is allowed by an event policy that targets this workflow
only:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') {
      actions_policies: [
        orgs.newRepoActionsPolicy('labeler') {
          include_workflows: [".github/workflows/labeler.yml"],
          allowed_events: ["pull_request_target"],
        },
      ],
    },
  ],
}
```

GitHub also offers the **Require lockfile** rule, which blocks the workflows that are not in the lockfile of their
repository, see [Enforce workflow lockfiles](https://docs.github.com/en/actions/how-tos/administer/enforce-workflow-lockfiles).
GitHub does not provide this rule in its API yet, so otterdog cannot configure it. A policy that requires it in the
web UI keeps it when otterdog updates the policy.

!!! info "Organization policy"

    Start a policy with `enforcement: "evaluate"` to see the runs it would block on the Policy insights page before
    enforcing it. This mode is only available with GitHub Enterprise Cloud, otherwise start with the repositories
    whose workflows are known.

## Approve workflows from forks

Pull requests from forks can run workflows. The setting `fork_pr_approval_policy` defines when a maintainer has to
approve such runs:

| Value                                    | Approval required for                                                                    |
|------------------------------------------|------------------------------------------------------------------------------------------|
| `first_time_contributors_new_to_github`  | users who are new to GitHub and never had a contribution merged in the repository         |
| `first_time_contributors`                | users who never had a contribution merged in the repository                              |
| `all_external_contributors`              | all users who are not members of the organization                                        |

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    workflows+: {
      fork_pr_approval_policy: "all_external_contributors",
    },
  },
}
```

!!! info "Organization policy"

    Requiring an approval for all external contributors gives maintainers a chance to review the changes before
    any workflow runs, at the cost of an additional step for every external pull request. It is especially
    relevant for repositories that use self-hosted runners, see
    [Approving workflow runs from forks](https://docs.github.com/en/organizations/managing-organization-settings/disabling-or-limiting-github-actions-for-your-organization#configuring-required-approval-for-workflows-from-public-forks).

## Disable GitHub Actions where it is not needed

Repositories that do not use workflows, e.g. mirrors, can disable GitHub Actions entirely:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-mirror') {
      workflows+: {
        enabled: false,
      },
    },
  ],
}
```

On organization level, `enabled_repositories` set to `selected` only enables GitHub Actions for the repositories
listed in `selected_repositories`.

## Cache size and costs

The setting `max_cache_size_gb` limits the total size of the GitHub Actions caches of a repository. Increasing it
may incur costs: depending on the setup of your otterdog installation, such changes require a review by a
designated team, see [Cost policy](../../operating_otterdog/setup.md#cost-policy).

Policies can enforce further restrictions on GitHub Actions, e.g. the
[usage of macOS large runners](../../reference/policies/macos-large-runners.md).

## Summary

| Setting                                    | Suggested value                                                 | Reason                                                |
|--------------------------------------------|-----------------------------------------------------------------|-------------------------------------------------------|
| `default_workflow_permissions`             | `read`                                                          | least privilege, grant more per workflow              |
| `actions_can_approve_pull_request_reviews` | `false`                                                         | approvals should come from people                     |
| `fork_pr_approval_policy`                  | `first_time_contributors` or stricter                           | review unknown code before it runs                    |
| `allowed_actions`                          | depends on your organization policy                             | trade-off between control and maintenance             |
| `sha_pinning_required`                     | `true`, once the actions of the workflows are pinned            | a tag can be moved to other code, a commit SHA cannot |
| `actions_policies`                         | restrict sensitive workflows to the actors and events they need | e.g. a release workflow run by maintainers only       |
