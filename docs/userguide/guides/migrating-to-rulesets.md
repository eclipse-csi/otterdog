# Migrating to rulesets

This guide describes how to replace [branch protection rules](../../reference/organization/repository/branch-protection-rule.md)
with [rulesets](../../reference/organization/repository/ruleset.md) in an otterdog configuration, without leaving a
branch unprotected. Read [Rulesets or branch protection rules](rulesets-vs-branch-protection.md) first to check
that rulesets cover your needs.

!!! warning

    Do not use the "Convert to ruleset" button of the GitHub web interface on repositories managed by otterdog. The
    created rulesets are not part of the configuration and are removed the next time the configuration is applied
    with deletions enabled, see [Otterdog specifics](rulesets-vs-branch-protection.md#otterdog-specifics).

## Overview

1. Map each branch protection rule to one or more rulesets.
2. Add the rulesets while keeping the branch protection rules.
3. Verify that the rulesets behave as expected.
4. Remove the branch protection rules in a separate change.

As GitHub enforces branch protection rules and rulesets together, adding the rulesets first never weakens the
protection: the most restrictive setting applies while both exist.

## Step 1: Map the properties

| Branch protection rule                                          | Ruleset                                                                                       |
|-----------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| `pattern`                                                       | `include_refs`: `refs/heads/<pattern>`, or `~DEFAULT_BRANCH` for the default branch           |
| `requires_pull_request: true`, `required_approving_review_count` | `required_pull_request+: { required_approving_review_count: ... }`                           |
| `requires_pull_request: false`                                  | `required_pull_request: null`                                                                 |
| `dismisses_stale_reviews`                                       | `required_pull_request.dismisses_stale_reviews`                                               |
| `requires_code_owner_reviews`                                   | `required_pull_request.requires_code_owner_review`                                            |
| `require_last_push_approval`                                    | `required_pull_request.requires_last_push_approval`                                           |
| `requires_conversation_resolution`                              | `required_pull_request.requires_review_thread_resolution`                                     |
| `requires_status_checks`, `required_status_checks`              | `required_status_checks+: { status_checks: [...] }`, or `null` if no check is required        |
| `requires_strict_status_checks`                                 | `required_status_checks.strict`                                                               |
| `requires_linear_history`, `requires_commit_signatures`         | same names                                                                                    |
| `requires_deployments`, `required_deployment_environments`      | same names                                                                                    |
| `allows_force_pushes`, `allows_deletions`                       | same names                                                                                    |
| `lock_branch`                                                   | `allows_updates: false`                                                                       |
| `restricts_pushes`, `push_restrictions`                         | `allows_updates: false`, with the allowed actors as `bypass_actors`                           |
| `blocks_creations`                                              | `allows_creations: false` (default), with the allowed actors as `bypass_actors`               |
| `bypass_pull_request_allowances`, `bypass_force_push_allowances` | `bypass_actors`, see [Exceptions](#exceptions)                                               |
| `is_admin_enforced: false`                                      | `#RepositoryAdmin` in `bypass_actors`, see [Exceptions](#exceptions)                          |
| `restricts_review_dismissals`, `review_dismissal_allowances`    | no equivalent                                                                                 |
| `lock_allows_fetch_and_merge`                                   | no equivalent                                                                                 |

Formats of status checks and actors are described in [Status Check](../../reference/organization/repository/status-check.md),
[Actor](../../reference/organization/repository/actor.md) and [Bypass Actor](../../reference/organization/repository/bypass-actor.md).

!!! note

    By default, a ruleset restricts the creation of matching branches to its bypass actors (`allows_creations` is
    `false`). This has no effect on the default branch, but set `allows_creations: true` for patterns like
    `refs/heads/release/*` if contributors could create such branches before.

### Exceptions

Exceptions work differently in both mechanisms:

- a branch protection rule exempts administrators unless `is_admin_enforced` is enabled, while a ruleset only
  exempts its bypass actors
- an allowance of a branch protection rule lifts a single requirement, e.g. the pull request requirement, while a
  bypass actor of a ruleset bypasses all rules of the ruleset

To keep an exception limited to a single requirement, put this requirement in a separate ruleset and add the bypass
actor only to this ruleset, as shown in the example below.

## Step 2: Add the rulesets

The following example migrates a typical rule of the default branch. The release app may push without a pull
request, and administrators are exempted, as with the original rule.

=== "Before"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-repo') {
          branch_protection_rules: [
            orgs.newBranchProtectionRule('main') {
              required_approving_review_count: 1,
              dismisses_stale_reviews: true,
              requires_strict_status_checks: true,
              required_status_checks+: [
                "build",
              ],
              requires_linear_history: true,
              bypass_pull_request_allowances+: [
                "my-release-app",
              ],
            },
          ],
        },
      ],
    }
    ```

=== "During the migration"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-repo') {
          branch_protection_rules: [
            orgs.newBranchProtectionRule('main') {
              required_approving_review_count: 1,
              dismisses_stale_reviews: true,
              requires_strict_status_checks: true,
              required_status_checks+: [
                "build",
              ],
              requires_linear_history: true,
              bypass_pull_request_allowances+: [
                "my-release-app",
              ],
            },
          ],
          rulesets: [
            orgs.newRepoRuleset('default-branch') {
              include_refs+: [
                "~DEFAULT_BRANCH",
              ],
              bypass_actors+: [
                "#RepositoryAdmin",
              ],
              required_pull_request: null,
              required_status_checks+: {
                strict: true,
                status_checks+: [
                  "build",
                ],
              },
              requires_linear_history: true,
            },
            orgs.newRepoRuleset('default-branch-reviews') {
              include_refs+: [
                "~DEFAULT_BRANCH",
              ],
              bypass_actors+: [
                "#RepositoryAdmin",
                "my-release-app",
              ],
              required_pull_request+: {
                required_approving_review_count: 1,
                dismisses_stale_reviews: true,
              },
              required_status_checks: null,
            },
          ],
        },
      ],
    }
    ```

=== "After"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-repo') {
          rulesets: [
            orgs.newRepoRuleset('default-branch') {
              include_refs+: [
                "~DEFAULT_BRANCH",
              ],
              bypass_actors+: [
                "#RepositoryAdmin", // (1)!
              ],
              required_pull_request: null,
              required_status_checks+: {
                strict: true,
                status_checks+: [
                  "build",
                ],
              },
              requires_linear_history: true,
            },
            orgs.newRepoRuleset('default-branch-reviews') {
              include_refs+: [
                "~DEFAULT_BRANCH",
              ],
              bypass_actors+: [
                "#RepositoryAdmin",
                "my-release-app", // (2)!
              ],
              required_pull_request+: {
                required_approving_review_count: 1,
                dismisses_stale_reviews: true,
              },
              required_status_checks: null,
            },
          ],
        },
      ],
    }
    ```

    1. Keeps the exemption of administrators of the original rule (`is_admin_enforced: false`). Remove it to
       enforce the rules for administrators as well.
    2. The release app may push without a pull request, but the rules of the first ruleset still apply to it.

Apply the change and check with `plan` that the only remaining differences are the new rulesets.

## Step 3: Verify

While the branch protection rule is still in place, check that the rulesets behave as expected:

- the rulesets are listed in the repository under **Settings > Rules > Rulesets**
- pull requests show the expected required reviews and checks, and automation can still push where intended
- for organizations on GitHub Enterprise, a ruleset can first be added with `enforcement: "evaluate"`: GitHub then
  only reports what the ruleset would block in the rule insights, see
  [Managing rulesets for a repository](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/managing-rulesets-for-a-repository),
  while the branch protection rule still protects the branch

## Step 4: Remove the branch protection rules

Remove the branch protection rules from the configuration in a separate change, once the rulesets have been
verified. The `plan` operation reports the removal as a deletion:

- when changes are applied after merging a pull request, deletions are applied automatically
- with the command line, `apply` only removes resources when `--delete-resources` is specified, see
  [Apply](../../reference/operations/apply.md)

## Common pitfalls

- **Status checks reported by apps**: keep the `<app-slug>:<check-name>` format of the original rule, otherwise any
  source can satisfy the check.
- **Renaming a ruleset**: the name identifies a ruleset, renaming it in the configuration deletes it and creates a
  new one.
- **Limits**: a repository can have up to 75 rulesets, see
  [About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets).
- **Organization-wide protections**: if many repositories share the same protection, consider an
  [organization ruleset](../../reference/organization/ruleset.md) for the common part instead of repeating it in every
  repository.
