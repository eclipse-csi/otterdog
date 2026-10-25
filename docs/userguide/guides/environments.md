# Deployment environments

A GitHub Actions job that references an [environment](../../reference/organization/repository/environment/index.md)
can only run once the protection rules of the environment are satisfied, and only then gets access to the secrets
of the environment. Environments are therefore the right place for credentials that deploy or publish something.

| Property                                       | Effect                                                                                             |
|------------------------------------------------|----------------------------------------------------------------------------------------------------|
| `deployment_branch_policy`, `branch_policies`  | `all`: no restriction, `protected`: only protected branches, `selected`: only the branches and tags listed in `branch_policies` |
| `reviewers`, `prevent_self_review`             | users or teams who must approve the job, optionally not the person who triggered it                |
| `wait_timer`                                   | minutes to wait before the job can run                                                              |
| `secrets`, `variables`                         | values only available to jobs that use the environment                                             |

Users with GitHub Free can only configure environments for public repositories, and some protection rules have
limited availability for private repositories, see
[Managing environments for deployment](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).

## Protect publishing credentials

The following environment is only available to workflows running for a tag starting with `v`, and requires the
approval of a release manager other than the person who triggered the workflow:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-library') {
      environments+: [
        orgs.newEnvironment('release') {
          deployment_branch_policy: "selected",
          branch_policies+: [
            "tag:v*", // (1)!
          ],
          reviewers+: [
            "@my-org/release-managers",
          ],
          prevent_self_review: true,
        },
      ],
    },
  ],
}
```

1. Patterns for tags start with `tag:`, see [Branch or Tag](../../reference/organization/repository/branch-or-tag.md).

The publishing job of the workflow then references the environment:

``` yaml
jobs:
  publish:
    runs-on: ubuntu-latest
    environment: release
    steps:
      ...
```

!!! warning

    An environment with `deployment_branch_policy: "all"` and no reviewers does not protect its secrets: a workflow
    running on any branch, e.g. a branch pushed by any user with write access, can use them. This also applies to
    environments used for publishing with OpenID Connect, as the trust configuration of the target system often
    identifies the repository, the workflow or the environment, but not the branch.

!!! tip "Recommendation"

    Restrict every environment that holds credentials or is trusted by an external system to the branches or tags
    that are allowed to deploy, and protect these branches and tags as well, see
    [Protecting branches](branch-protection.md) and [Protecting tags and releases](tag-protection.md).

## Require a manual approval

An environment without secrets can serve as a manual approval step, e.g. before an expensive workflow runs or
before a workflow runs with elevated permissions:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') {
      environments+: [
        orgs.newEnvironment('manual-approval') {
          reviewers+: [
            "@my-org/maintainers",
          ],
        },
      ],
    },
  ],
}
```

Up to 6 users or teams can be listed as reviewers, and the approval of one of them is sufficient.

## GitHub Pages

When GitHub Pages is enabled for a repository, GitHub automatically creates an environment named `github-pages`.
Declare it in the configuration, otherwise `plan` reports it as a resource to delete:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-website') {
      gh_pages_build_type: "workflow",
      environments+: [
        orgs.newEnvironment('github-pages') {
          deployment_branch_policy: "selected",
          branch_policies+: [
            "main",
          ],
        },
      ],
    },
  ],
}
```

See [Common repository patterns](repository-patterns.md#websites-with-github-pages) for the other GitHub Pages
settings.

## Require a successful deployment before merging

A ruleset or a branch protection rule can require that changes were successfully deployed to an environment before
they are merged. The required environments must be defined in the same repository:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-service') {
      environments+: [
        orgs.newEnvironment('staging'),
      ],
      rulesets: [
        orgs.newRepoRuleset('default-branch') {
          include_refs+: [
            "~DEFAULT_BRANCH",
          ],
          required_pull_request+: {
            required_approving_review_count: 1,
          },
          required_status_checks: null,
          requires_deployments: true,
          required_deployment_environments+: [
            "staging",
          ],
        },
      ],
    },
  ],
}
```

## Environments created by GitHub features

Besides `github-pages`, some GitHub features create or use environments with a specific name. Before removing such
an environment from the configuration, check whether it is still used. For example, GitHub moved the secrets of the
Copilot cloud agent from an environment named `copilot` to dedicated agent secrets, see the
[GitHub changelog](https://github.blog/changelog/2026-05-11-more-flexible-secrets-and-variables-for-copilot-cloud-agent/).
