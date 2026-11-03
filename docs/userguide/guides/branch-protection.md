# Protecting branches

Otterdog supports both mechanisms that GitHub offers to protect branches:
[repository rulesets](../../reference/organization/repository/ruleset.md) and
[branch protection rules](../../reference/organization/repository/branch-protection-rule.md). This guide shows
common protections with both mechanisms. To choose between them, see
[Rulesets or branch protection rules](rulesets-vs-branch-protection.md).

## Before you start

Answer the following questions before writing a protection:

- **Which branches?** Usually the default branch, sometimes also maintenance or release branches.
- **Which workflow?** Direct pushes, pull requests with reviews, or pull requests without mandatory review.
- **Which checks?** The exact names of the status checks that must pass, see
  [Status Check](../../reference/organization/repository/status-check.md).
- **Who may bypass the protection?** Release automation, maintainers, administrators, or nobody.

## Prevent force pushes and deletions

The minimal protection keeps the history of a branch intact without imposing a pull request workflow: users with
write access can still push directly, but they cannot rewrite the history or delete the branch.

=== "Ruleset"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-repo') {
          rulesets: [
            orgs.newRepoRuleset('default-branch') {
              include_refs+: [
                "~DEFAULT_BRANCH",
              ],
              required_pull_request: null, // (1)!
              required_status_checks: null,
            },
          ],
        },
      ],
    }
    ```

    1. Without a pull request requirement and without status checks, the ruleset only blocks force pushes and
       deletions, which are blocked by default (`allows_force_pushes` and `allows_deletions` are `false`).

=== "Branch protection rule"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-repo') {
          branch_protection_rules: [
            orgs.newBranchProtectionRule('main') {
              requires_pull_request: false,
              required_approving_review_count: null, // (1)!
              requires_status_checks: false,
            },
          ],
        },
      ],
    }
    ```

    1. Must be `null` when `requires_pull_request` is disabled, see the validation rules of
       [Branch Protection Rule](../../reference/organization/repository/branch-protection-rule.md#validation-rules).

!!! tip "Recommendation"

    Protect at least the default branch of every active repository against force pushes and deletions. This
    protection does not change the way people work, but prevents the accidental loss of history.

## Require pull requests and reviews

Requiring a pull request ensures that every change is visible and checked before it reaches the branch. The
following example requires one approval, dismisses approvals when new commits are pushed and requires that the
most recent push is approved by someone else than its author.

=== "Ruleset"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-repo') {
          rulesets: [
            orgs.newRepoRuleset('default-branch') {
              include_refs+: [
                "~DEFAULT_BRANCH",
              ],
              required_pull_request+: {
                required_approving_review_count: 1,
                dismisses_stale_reviews: true,
                requires_last_push_approval: true,
              },
              required_status_checks: null,
            },
          ],
        },
      ],
    }
    ```

=== "Branch protection rule"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-repo') {
          branch_protection_rules: [
            orgs.newBranchProtectionRule('main') {
              required_approving_review_count: 1,
              dismisses_stale_reviews: true,
              require_last_push_approval: true,
              requires_status_checks: false,
            },
          ],
        },
      ],
    }
    ```

!!! info "Organization policy"

    The number of required approvals is a trade-off between assurance and the capacity of the team:

    - `0` requires a pull request, so that checks run and changes are visible, but no review.
    - `1` requires a second person to look at every change.
    - `2` or more increases assurance, but can block small teams.

    The example default configuration requires 2 approvals. Choose a value that the team can sustain, as a
    requirement that cannot be met tends to be bypassed.

Further options of the pull request requirement:

| Need                                                    | Ruleset (`required_pull_request`)       | Branch protection rule              |
|---------------------------------------------------------|-----------------------------------------|-------------------------------------|
| Request a review of the code owners                     | `requires_code_owner_review`            | `requires_code_owner_reviews`       |
| Resolve all review conversations before merging         | `requires_review_thread_resolution`     | `requires_conversation_resolution`  |
| Restrict the merge methods of pull requests             | `allowed_merge_methods`                 | not available                       |

Code owner reviews require a `CODEOWNERS` file in the repository, see
[About code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners).
The merge methods available for all branches of a repository are configured by the repository settings
`allow_merge_commit`, `allow_squash_merge` and `allow_rebase_merge`.

## Require status checks

Required status checks ensure that continuous integration succeeded before a change is merged.

=== "Ruleset"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
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
                strict: true, // (1)!
                status_checks+: [
                  "build",
                  "test / unit-tests",
                ],
              },
            },
          ],
        },
      ],
    }
    ```

    1. Requires the branch of the pull request to be up to date with the target branch before merging.

=== "Branch protection rule"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-repo') {
          branch_protection_rules: [
            orgs.newBranchProtectionRule('main') {
              required_approving_review_count: 1,
              requires_status_checks: true,
              requires_strict_status_checks: true, // (1)!
              required_status_checks+: [
                "build",
                "test / unit-tests",
              ],
            },
          ],
        },
      ],
    }
    ```

    1. Requires the branch of the pull request to be up to date with the target branch before merging.

The names of the checks must exactly match the names reported to GitHub, see
[Status Check](../../reference/organization/repository/status-check.md) for the naming rules of workflow jobs.

!!! warning

    A required check that never reports a status blocks the merge of every pull request. This happens for example
    when a workflow is skipped because of path or branch filters, see
    [Handling skipped but required checks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks#handling-skipped-but-required-checks).

!!! tip "Recommendation"

    When a check is reported by a GitHub App, use the format `<app-slug>:<check-name>`, so that only this app
    can satisfy the check.

Requiring up-to-date branches (`strict`) guarantees that the checks ran against the latest state of the target
branch, at the cost of more rebases and CI runs in busy repositories. A
[merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)
provides the same guarantee without requiring authors to update their branches. Otterdog supports merge queues
for rulesets only, see `required_merge_queue` in [Repository Ruleset](../../reference/organization/repository/ruleset.md).

## Require code scanning results and Copilot reviews

Rulesets can also block merges on the results of code scanning, and request a review from Copilot automatically
for new pull requests.

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
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
          required_code_scanning: orgs.newCodeScanning() {
            code_scanning_tools+: [
              "CodeQL:high_or_higher:errors", // (1)!
            ],
          },
          copilot_code_review: orgs.newCopilotCodeReview() {
            review_on_push: true, // (2)!
          },
        },
      ],
    },
  ],
}
```

1. Blocks the merge if CodeQL reports security alerts of severity high or critical, or alerts of severity error.
2. Copilot also reviews the new pushes to a pull request, not only its first version.

Code scanning has to be set up for the repository, see [Repository security features](repository-security.md).
Copilot only reviews the pull requests of authors that have access to Copilot code review.

## Require code quality, coverage and license compliance

Repository rulesets can block merges on the code quality results, the line coverage and the license compliance
of the dependencies of a pull request:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    plan: "enterprise", // (1)!
  },
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
          required_code_quality: orgs.newCodeQuality() {
            severity: "warnings", // (2)!
          },
          required_code_coverage: orgs.newCodeCoverage() {
            minimum_coverage: 80, // (3)!
            max_coverage_drop: 1,
          },
          requires_license_compliance_scanning: true, // (4)!
        },
      ],
    },
  ],
}
```

1. Read-only property that reflects the billing plan of the organization. The code quality and code coverage rules
   require at least GitHub Team, the license compliance rule GitHub Enterprise, `validate` warns otherwise.
2. Code quality results of severity warning or error must be resolved before a pull request can be merged.
3. A pull request is blocked if its line coverage is below 80 %, or drops by more than 1 percentage point compared
   to the default branch. GitHub does not wait for coverage uploads: make the checks that upload coverage data
   required status checks. This rule is in public preview on GitHub.
4. The dependencies added or changed by a pull request must comply with the license policy of the organization.

These rules are only supported by repository rulesets, not by organization rulesets.

## Restrict commit messages and branch names

Patterns can enforce conventions for the metadata of commits, e.g. their message or the email of their author,
and for the names of branches:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    plan: "enterprise", // (1)!
  },
  _repositories+:: [
    orgs.newRepo('my-repo') {
      rulesets: [
        orgs.newRepoRuleset('commit-messages') {
          include_refs+: [
            "~DEFAULT_BRANCH",
          ],
          required_pull_request: null,
          required_status_checks: null,
          commit_message_pattern: orgs.newPattern() {
            name: "Conventional Commits",
            operator: "regex", // (2)!
            pattern: "^(feat|fix|docs|chore|refactor|test|ci|build|perf|revert)(\\(.+\\))?!?: ",
          },
        },
        orgs.newRepoRuleset('branch-names') {
          include_refs+: [
            "~ALL",
          ],
          exclude_refs+: [
            "~DEFAULT_BRANCH",
          ],
          allows_creations: true, // (3)!
          allows_deletions: true,
          allows_force_pushes: true,
          required_pull_request: null,
          required_status_checks: null,
          branch_name_pattern: orgs.newPattern() {
            name: "Branch prefix",
            operator: "regex",
            pattern: "^(feature|fix|release|dependabot)/", // (4)!
          },
        },
      ],
    },
  ],
}
```

1. Read-only property that reflects the billing plan of the organization. Restricting the metadata of commits and
   the names of branches requires GitHub Enterprise, `validate` warns otherwise.
2. The operator is one of `starts_with`, `ends_with`, `contains` or `regex`, set `negate: true` to reject the
   values that match the pattern instead, see
   [Pattern Settings](../../reference/organization/repository/ruleset.md#pattern-settings).
3. The ruleset only restricts the names of branches: creating, deleting and force pushing branches stay allowed.
4. Branches created by automation, e.g. Dependabot, must match the pattern too.

`commit_author_email_pattern` and `committer_email_pattern` restrict the emails of the commits in the same way.
A branch name pattern is only supported by rulesets with `target: "branch"`.

## Restrict the files that can be pushed

A ruleset with target `push` blocks pushes that add files matching restricted paths or extensions, or files that
are too large, to any branch of the repository. Push rulesets are only available for private and internal
repositories.

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    plan: "team", // (1)!
  },
  _repositories+:: [
    orgs.newRepo('my-repo') {
      private: true, // (2)!
      allow_forking: false,
      rulesets: [
        orgs.newRepoRuleset('restrict-files') {
          target: "push",
          allows_creations: true, // (3)!
          allows_deletions: true,
          allows_force_pushes: true,
          required_pull_request: null,
          required_status_checks: null,
          restricted_file_extensions+: [
            "*.exe",
            "*.jar",
          ],
          max_file_size: 10, // (4)!
          max_file_size_exceptions+: [
            "docs/assets/**",
          ],
        },
      ],
    },
  ],
}
```

1. Read-only property that reflects the billing plan of the organization. Push rulesets require at least GitHub
   Team, `validate` warns otherwise.
2. Push rulesets require a private or internal repository. The default settings of an organization disable the
   forking of private repositories.
3. A push ruleset only supports push rules, the branch rules required by `orgs.newRepoRuleset` have to be disabled.
4. The maximum size of a file in megabytes, files stored with Git LFS are not limited.

## Protect maintenance and release branches

Maintenance branches often need the same protection as the default branch. A ruleset can protect several branch
patterns at once, while a branch protection rule matches a single pattern.

=== "Ruleset"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-repo') {
          rulesets: [
            orgs.newRepoRuleset('protected-branches') {
              include_refs+: [
                "~DEFAULT_BRANCH",
                "refs/heads/release/*",
              ],
              allows_creations: true, // (1)!
              required_pull_request+: {
                required_approving_review_count: 1,
              },
              required_status_checks: null,
            },
          ],
        },
      ],
    }
    ```

    1. By default, only bypass actors can create branches that match a ruleset. Allow creations if contributors
       should be able to create new release branches.

=== "Branch protection rule"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-repo') {
          branch_protection_rules: [
            orgs.newBranchProtectionRule('main') {
              required_approving_review_count: 1,
              requires_status_checks: false,
            },
            orgs.newBranchProtectionRule('release/*') {
              required_approving_review_count: 1,
              requires_status_checks: false,
            },
          ],
        },
      ],
    }
    ```

Patterns follow the `fnmatch` syntax with the `File::FNM_PATHNAME` flag: `*` does not match `/`. Use
`release/**/*` to match nested names like `release/1.x/fixes`, see
[About branch protection rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule#about-branch-protection-rules).

!!! note

    Only one branch protection rule applies to a branch: a rule that names the branch exactly takes precedence
    over patterns, and among patterns the rule created first wins. All matching rulesets apply together, and the
    most restrictive version of each rule is enforced. Restricting the creation of matching
    branches is done with `allows_creations` for rulesets, and with `restricts_pushes` and `blocks_creations`
    for branch protection rules.

## Allow automation to push

Release automation sometimes needs to push to a protected branch, e.g. to commit a version change. Grant such an
exception to the narrowest possible actor.

=== "Ruleset"

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
                "my-release-app", // (1)!
                "@my-org/release-managers:pull_request", // (2)!
              ],
              required_pull_request+: {
                required_approving_review_count: 1,
              },
              required_status_checks: null,
            },
          ],
        },
      ],
    }
    ```

    1. A GitHub App, referenced by its slug, can always bypass the ruleset.
    2. Members of this team can only bypass the ruleset when merging a pull request, not by pushing directly.

=== "Branch protection rule"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-repo') {
          branch_protection_rules: [
            orgs.newBranchProtectionRule('main') {
              required_approving_review_count: 1,
              requires_status_checks: false,
              bypass_pull_request_allowances+: [
                "my-release-app",
              ],
            },
          ],
        },
      ],
    }
    ```

See [Bypass Actor](../../reference/organization/repository/bypass-actor.md) and
[Actor](../../reference/organization/repository/actor.md) for the supported formats. The two mechanisms differ:

- a **ruleset** bypass actor bypasses all rules of the ruleset, either always or only when merging a pull request
- a **branch protection rule** bypass allowance only lifts the pull request requirement, required status checks
  still apply

!!! tip "Recommendation"

    Prefer a GitHub App or a dedicated team over individual user accounts as bypass actors: their permissions can
    be reviewed and revoked without changing the protection, and they do not depend on a single person.

!!! warning

    Avoid repository roles such as `#Write` as bypass actors of a ruleset that requires pull requests: every user
    with this role could then merge without review, which makes the requirement optional.

## Read-only branches and mirrors

Some branches must not receive changes at all, e.g. a branch that is mirrored from another system or a frozen
maintenance branch.

=== "Ruleset"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-mirror') {
          rulesets: [
            orgs.newRepoRuleset('read-only') {
              include_refs+: [
                "~ALL",
              ],
              allows_updates: false,
              bypass_actors+: [
                "my-mirror-app", // (1)!
              ],
              required_pull_request: null,
              required_status_checks: null,
            },
          ],
        },
      ],
    }
    ```

    1. Only the app that synchronizes the mirror can push.

=== "Branch protection rule"

    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-mirror') {
          branch_protection_rules: [
            orgs.newBranchProtectionRule('main') {
              requires_pull_request: false,
              required_approving_review_count: null,
              requires_status_checks: false,
              restricts_pushes: true,
              push_restrictions+: [
                "my-mirror-app", // (1)!
              ],
            },
          ],
        },
      ],
    }
    ```

    1. Only the app that synchronizes the mirror can push.

A branch protection rule can also lock a branch completely with `lock_branch`, see
[Branch Protection Rule](../../reference/organization/repository/branch-protection-rule.md). Restricting who can
push to a branch is only available for repositories owned by an organization, see
[About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#restrict-who-can-push-to-matching-branches).

## Administrators

The two mechanisms treat administrators differently:

- a **branch protection rule** does not apply to repository administrators and roles with the "bypass branch
  protections" permission, unless `is_admin_enforced` is enabled
- a **ruleset** applies to everybody, except the actors listed in `bypass_actors`, e.g. `#RepositoryAdmin`
  or `#OrganizationAdmin`

!!! info "Organization policy"

    Exempting administrators allows fixing a broken branch quickly, while enforcing the protection for them
    guarantees that every change follows the same process. If administrators need an exemption, make it explicit
    as a bypass actor of a ruleset, which is visible to everybody with read access to the repository.

## Common pitfalls

- **Default branch renamed**: a branch protection rule matches a branch name or pattern and must be updated when
  the default branch is renamed, while `~DEFAULT_BRANCH` in a ruleset always follows the default branch.
- **Ignored settings**: when `requires_pull_request` or `requires_status_checks` is disabled in a branch
  protection rule, the related settings are ignored, and `validate` reports them.
- **Archived repositories**: GitHub does not allow changes to archived repositories, otterdog ignores their branch
  protection rules.
- **Protections defined outside otterdog**: as otterdog manages all branch protection rules and rulesets of a
  repository, protections created in the GitHub web interface are removed when the configuration is applied with
  deletions enabled, see [Rulesets or branch protection rules](rulesets-vs-branch-protection.md#otterdog-specifics).
