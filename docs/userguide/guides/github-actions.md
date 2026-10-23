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
The GitHub policy that requires actions to be pinned to a full-length commit SHA cannot be configured with otterdog.

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

| Setting                                    | Suggested value                                      | Reason                                                  |
|--------------------------------------------|------------------------------------------------------|---------------------------------------------------------|
| `default_workflow_permissions`             | `read`                                               | least privilege, grant more per workflow                |
| `actions_can_approve_pull_request_reviews` | `false`                                              | approvals should come from people                       |
| `fork_pr_approval_policy`                  | `first_time_contributors` or stricter                | review unknown code before it runs                      |
| `allowed_actions`                          | depends on your organization policy                  | trade-off between control and maintenance               |
