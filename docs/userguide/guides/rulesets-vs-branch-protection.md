# Rulesets or branch protection rules

GitHub offers two mechanisms to protect branches: branch protection rules and rulesets. Both are supported by
GitHub and by otterdog. GitHub describes rulesets as a more flexible way to manage protections and provides a
tool to [convert branch protection rules to rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/converting-branch-protections-to-rulesets),
but branch protection rules are not deprecated. Tag protection rules, on the other hand, have been retired by
GitHub and replaced by tag rulesets, see [Protecting tags and releases](tag-protection.md).

This guide compares both mechanisms and lists what otterdog supports. To migrate existing rules, see
[Migrating to rulesets](migrating-to-rulesets.md).

## Comparison

|                              | Branch protection rules                                         | Rulesets                                                                  |
|------------------------------|-----------------------------------------------------------------|---------------------------------------------------------------------------|
| Rules applying to a branch   | one rule per branch                                             | all matching rulesets, combined with branch protection rules             |
| Conflicting settings         | not applicable                                                  | the most restrictive version of each rule applies                        |
| Targets                      | branches                                                        | branches and tags, pushes for private and internal repositories          |
| Scope                        | repository                                                      | repository, organization or enterprise                                   |
| Default branch               | matched by name or pattern                                      | `~DEFAULT_BRANCH` follows the default branch                             |
| Exceptions                   | administrators exempted unless `is_admin_enforced`, allowances per setting | bypass list of roles, teams, users or apps, always or for pull requests only |
| Visibility                   | repository settings                                             | anyone with read access can view active rulesets                         |
| Temporary deactivation       | remove the rule                                                 | enforcement `disabled`, or `evaluate` to only report violations          |
| Merge queue in otterdog      | not supported                                                   | `required_merge_queue`                                                    |

See [About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
and [About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
for a complete description.

Rulesets can protect the same branch several times, e.g. an organization ruleset defines a common baseline and a
repository ruleset adds the checks of the repository:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    plan: "enterprise", // (1)!
  },
  rulesets+: [
    orgs.newOrgRuleset('baseline') {
      include_repo_names+: [
        "~ALL",
      ],
      include_refs+: [
        "~DEFAULT_BRANCH",
      ],
      required_pull_request: null, // (2)!
      required_status_checks: null,
    },
  ],
  _repositories+:: [
    orgs.newRepo('my-repo') {
      rulesets: [
        orgs.newRepoRuleset('default-branch') {
          include_refs+: [
            "~DEFAULT_BRANCH",
          ],
          required_pull_request+: {
            required_approving_review_count: 1,
          },
          required_status_checks+: {
            status_checks+: [
              "build",
            ],
          },
        },
      ],
    },
  ],
}
```

1. Read-only property that reflects the billing plan of the organization. Otterdog currently only accepts
   organization rulesets for organizations on the `enterprise` plan.
2. The baseline blocks force pushes and deletions of the default branch in all repositories.

## Availability by GitHub plan

| Feature                                                              | Availability on GitHub                                                                                        |
|----------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| Branch protection rules and rulesets                                 | public repositories with GitHub Free, public and private repositories with GitHub Pro, Team and Enterprise    |
| Organization rulesets                                                | GitHub Team and GitHub Enterprise                                                                             |
| Push rulesets                                                        | private and internal repositories with GitHub Team and GitHub Enterprise                                      |
| Metadata restrictions (commit message, emails, branch and tag names) | GitHub Enterprise                                                                                             |
| Code quality and code coverage rules                                 | GitHub Team and GitHub Enterprise, repository rulesets only                                                   |
| License compliance rule                                              | GitHub Enterprise, repository rulesets only                                                                   |
| Required workflows rule                                              | organization rulesets only                                                                                    |
| Enforcement `evaluate`                                               | GitHub Enterprise                                                                                             |
| Merge queue                                                          | public repositories owned by an organization, private repositories with GitHub Enterprise Cloud               |

`validate` warns about the rules of a ruleset that require a higher plan than the `plan` of the organization in its
configuration, it does not warn if neither the configuration nor its default configuration sets `plan`, see
[Organization Settings](../../reference/organization/settings.md). `validate` reports push rules for a public
repository as an error, whatever the plan.
Plans change over time, check the GitHub documentation before relying on a feature:
[About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets),
[Organization rulesets for GitHub Team](https://github.blog/changelog/2025-06-16-organization-rulesets-now-available-for-github-team-plans/),
[Managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).

## Otterdog specifics

Otterdog does not support all features of rulesets. The following table lists the rules that can be configured:

| Rule on GitHub                                                   | Ruleset property in otterdog                                                       |
|------------------------------------------------------------------|------------------------------------------------------------------------------------|
| Restrict creations, updates and deletions                        | `allows_creations`, `allows_updates`, `allows_deletions`                           |
| Block force pushes                                               | `allows_force_pushes`                                                              |
| Require linear history                                           | `requires_linear_history`                                                          |
| Require signed commits                                           | `requires_commit_signatures`                                                       |
| Require deployments to succeed                                   | `requires_deployments`, `required_deployment_environments`                         |
| Require a pull request before merging                            | `required_pull_request`                                                            |
| Require status checks to pass                                    | `required_status_checks`                                                           |
| Require merge queue                                              | `required_merge_queue`                                                             |
| Automatically request Copilot code review                        | `copilot_code_review`                                                              |
| Restrict commit metadata                                         | `commit_message_pattern`, `commit_author_email_pattern`, `committer_email_pattern` |
| Restrict branch names, restrict tag names                        | `branch_name_pattern`, `tag_name_pattern`                                          |
| Require code scanning results                                    | `required_code_scanning`                                                           |
| Require code quality results                                     | `required_code_quality`                                                            |
| Restrict code coverage                                           | `required_code_coverage`                                                           |
| Require license compliance results                               | `requires_license_compliance_scanning`                                             |
| Require workflows to pass before merging (organization rulesets) | `required_workflows`                                                               |
| Restrict file paths (push rulesets)                              | `restricted_file_paths`, `restricted_file_paths_exceptions`                        |
| Restrict file path length (push rulesets)                        | `max_file_path_length`                                                             |
| Restrict file extensions (push rulesets)                         | `restricted_file_extensions`                                                       |
| Restrict file size (push rulesets)                               | `max_file_size`, `max_file_size_exceptions`                                        |

The following features cannot be configured with otterdog:

- the parameter `update_allows_fetch_and_merge` of the rule restricting updates and the required reviewers of
  the rule requiring a pull request
- targeting the repositories of an organization ruleset by custom properties, only repository names are supported
- deploy keys as bypass actors

!!! warning

    Otterdog manages all rulesets and branch protection rules of the repositories and the organization:

    - a protection created in the GitHub web interface, including with the "Convert to ruleset" button, is not part
      of the configuration: `plan` reports it as a deletion, and it is removed when the configuration is applied
      with deletions enabled (`--delete-resources` for the command line, always for changes applied after merging
      a pull request)
    - otterdog updates a ruleset by sending its complete definition, so rules that otterdog does not support and
      that were added to a managed ruleset in the web interface are removed when the ruleset is updated

    Make all changes to protections through the configuration.

## When to prefer rulesets

Rulesets are the better fit when:

- several protections must apply to the same branch, e.g. an organization baseline and repository specifics
- tags must be protected
- pull requests should go through a merge queue
- exceptions must be explicit and visible, e.g. a release app or a team that may only bypass through pull requests
- a protection should be tested before it is enforced, with the `evaluate` enforcement
- the protection should follow the default branch, even if it is renamed

## When branch protection rules remain a good choice

- Existing rules that meet the needs of the project: there is no deprecation that requires migrating them.
- Otterdog has no ruleset equivalent for restricting who can dismiss reviews (`restricts_review_dismissals`) and for
  allowing fork syncing on a locked branch (`lock_allows_fetch_and_merge`).

!!! tip "Recommendation"

    For new protections, prefer rulesets when your GitHub plan supports them. Avoid protecting the same branch with
    both mechanisms in the long term: GitHub enforces both, but the effective protection becomes harder to review.
    Combining them is useful during a migration.
