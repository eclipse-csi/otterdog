# Pull requests and merging

How pull requests are merged shapes the history of a repository: which commits it contains, which messages they
carry and whether it stays linear. These [repository](../../reference/organization/repository/index.md) settings
complement the protection of branches, which defines whether a pull request is required, see
[Protecting branches](branch-protection.md).

| Need                                                       | Settings                                                                     |
|------------------------------------------------------------|------------------------------------------------------------------------------|
| Choose how pull requests are merged                        | `allow_merge_commit`, `allow_squash_merge`, `allow_rebase_merge`             |
| Restrict the merge methods of protected branches           | `allowed_merge_methods` of a ruleset                                         |
| Control the messages of merge and squash commits           | `merge_commit_title`, `merge_commit_message`, `squash_merge_commit_title`, `squash_merge_commit_message` |
| Merge pull requests once their requirements are met        | `allow_auto_merge`                                                           |
| Keep pull requests up to date with their base branch       | `allow_update_branch`                                                        |
| Delete the branch of a merged pull request                 | `delete_branch_on_merge`                                                     |
| Merge pull requests through a queue                        | `required_merge_queue` of a ruleset                                          |

These settings are not available for archived repositories, otterdog ignores them for these repositories.

## Choose the merge methods

GitHub offers three ways to merge a pull request, each one can be allowed or not per repository, see
[About merge methods on GitHub](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/about-merge-methods-on-github):

| Method       | Setting              | History of the base branch                                        |
|--------------|----------------------|-------------------------------------------------------------------|
| Merge commit | `allow_merge_commit` | all commits of the pull request, joined by a merge commit         |
| Squash       | `allow_squash_merge` | a single commit for the whole pull request                        |
| Rebase       | `allow_rebase_merge` | all commits of the pull request, rewritten on top of the base     |

The following repository only allows squash merges, so that each pull request results in a single commit:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') {
      allow_merge_commit: false,
      allow_rebase_merge: false,
      allow_squash_merge: true,
    },
  ],
}
```

A protection that requires a linear history (`requires_linear_history`) rejects merge commits: allow squash or
rebase merges in repositories that require it.

!!! info "Organization policy"

    Squash merges keep the history of the base branch readable, one commit per change, but lose the individual
    commits of a pull request. Merge commits and rebase merges keep them, which helps to review the history of large
    changes. Allowing a single method makes the history predictable, allowing several leaves the choice to whoever
    merges.

## Restrict the merge methods of protected branches

The repository settings apply to all branches. A ruleset can further restrict the merge methods of the branches it
protects with `allowed_merge_methods`, e.g. to require squash merges into the default branch while maintenance
branches also accept merge commits:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') {
      allow_merge_commit: true,
      allow_squash_merge: true,
      rulesets: [
        orgs.newRepoRuleset('main') {
          include_refs+: [
            "~DEFAULT_BRANCH",
          ],
          required_pull_request+: {
            allowed_merge_methods: [
              "squash", // (1)!
            ],
          },
          required_status_checks: null,
        },
      ],
    },
  ],
}
```

1. Allowed values are `merge`, `squash` and `rebase`. A method that the repository does not allow cannot be used,
   whatever the ruleset allows.

## Control the messages of merge and squash commits

By default, GitHub builds the message of a squash commit from the commits of the pull request. To use the title
and description of the pull request instead, e.g. when pull request titles follow a convention:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') {
      squash_merge_commit_title: "PR_TITLE",
      squash_merge_commit_message: "PR_BODY",
    },
  ],
}
```

GitHub only accepts some combinations of title and message, `validate` reports the others as error:

| Commit       | Title                                         | Message                                          |
|--------------|-----------------------------------------------|--------------------------------------------------|
| Squash       | `PR_TITLE`                                    | `PR_BODY`, `BLANK` or `COMMIT_MESSAGES`          |
| Squash       | `COMMIT_OR_PR_TITLE`                          | `COMMIT_MESSAGES`                                |
| Merge commit | `PR_TITLE`                                    | `PR_BODY` or `BLANK`                             |
| Merge commit | `MERGE_MESSAGE`                               | `PR_TITLE`                                       |

`COMMIT_OR_PR_TITLE` uses the title of the commit if the pull request has a single commit, the title of the pull
request otherwise.

## Merge pull requests once their requirements are met

With `allow_auto_merge`, the author of a pull request can enable auto-merge, so that GitHub merges the pull request
as soon as the required reviews and status checks are satisfied, see
[Automatically merging a pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request).
Auto-merge is only useful for branches whose protection requires reviews or status checks:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') {
      allow_auto_merge: true,
      allow_update_branch: true, // (1)!
      rulesets: [
        orgs.newRepoRuleset('main') {
          include_refs+: [
            "~DEFAULT_BRANCH",
          ],
          required_status_checks+: {
            strict: true, // (2)!
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

1. Shows the "Update branch" button on pull requests whose branch is behind the base branch.
2. Requires the branch of a pull request to be up to date with the base branch before merging. Combined with
   auto-merge, an outdated pull request waits until its branch is updated.

Auto-merge is available for public repositories, and for private repositories with a paid GitHub plan.

## Delete the branch of a merged pull request

`delete_branch_on_merge` deletes the head branch of a pull request once it is merged, which keeps the list of
branches short. A deleted branch can be restored from the pull request. The example default configuration enables
it for all repositories.

## Merge pull requests through a queue

A merge queue merges pull requests one after the other, or in groups, after running the required status checks on
the result of the merge, see
[Managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).
It is configured with `required_merge_queue` in a ruleset, branch protection rules do not support it in otterdog:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') {
      rulesets: [
        orgs.newRepoRuleset('main') {
          include_refs+: [
            "~DEFAULT_BRANCH",
          ],
          required_status_checks+: {
            status_checks+: [
              "build",
            ],
          },
          required_merge_queue: orgs.newMergeQueue() {
            merge_method: "SQUASH", // (1)!
            max_group_size: 3,
          },
        },
      ],
    },
  ],
}
```

1. `MERGE`, `SQUASH` or `REBASE`. The other settings of `orgs.newMergeQueue()`, e.g. `build_concurrency` and
   `status_check_timeout`, come from the default configuration.

!!! warning

    The required status checks must also run for the merge queue: the workflows that report them need the
    `merge_group` event as trigger, otherwise the queued pull requests wait for checks that never run and are
    removed from the queue after `status_check_timeout` minutes.

The merge queue is available for public repositories owned by an organization, and for private repositories with
GitHub Enterprise Cloud.
