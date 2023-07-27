Definition of a Branch Protection Rule, the following properties are supported:

| Key                                | Value                                  | Description                                                                                  | Notes                                                                                                                                                                                                                                                                                                                |
|------------------------------------|----------------------------------------|----------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| _pattern_                          | string                                 | Pattern to match branches                                                                    | Pattern follows [fnmatch syntax](https://ruby-doc.org/core-2.5.1/File.html#method-c-fnmatch), see [doc@GitHub](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule#about-branch-protection-rules) for more info |
| _allows_deletions_                 | boolean                                | Allows deletion of the protected branch by anyone with write access to the repository        |                                                                                                                                                                                                                                                                                                                      |
| _allows_force_pushes_              | boolean                                | If branch allows force pushes                                                                |                                                                                                                                                                                                                                                                                                                      |
| _bypass_force_push_allowances_     | list\[[Actor](actor.md)\]              | List of actors able to force push for this branch protection rule                            |                                                                                                                                                                                                                                                                                                                      |
| _bypass_pull_request_allowances_   | list\[[Actor](actor.md)\]              | List of actors able to bypass PRs for this branch protection rule                            |                                                                                                                                                                                                                                                                                                                      |
| _dismisses_stale_reviews_          | boolean                                | Dismiss approved reviews automatically when a new commit is pushed                           |                                                                                                                                                                                                                                                                                                                      |
| _is_admin_enforced_                | boolean                                | Enforces the branch protection rule for admins                                               |                                                                                                                                                                                                                                                                                                                      |
| _lock_allows_fetch_and_merge_      | boolean                                | If the repo has dependabot alerts enabled                                                    |                                                                                                                                                                                                                                                                                                                      |
| _lock_branch_                      | boolean                                | If the branch is read-only                                                                   |                                                                                                                                                                                                                                                                                                                      |
| _push_restrictions_                | list\[[Actor](actor.md)\]              | List of actors that are permitted to push to the branch                                      |                                                                                                                                                                                                                                                                                                                      |
| _require_last_push_approval_       | boolean                                | Whether the most recent push must be approved by someone other than the person who pushed it |                                                                                                                                                                                                                                                                                                                      |
| _requires_approving_reviews_       | boolean                                | TBD                                                                                          |                                                                                                                                                                                                                                                                                                                      |
| _required_approving_review_count_  | integer or null                        | TBD                                                                                          |                                                                                                                                                                                                                                                                                                                      |
| _requires_code_owner_reviews_      | boolean                                | If reviews from code owners are required to update matching branches                         |                                                                                                                                                                                                                                                                                                                      |
| _requires_commit_signatures_       | boolean                                | If commits are required to be signed                                                         |                                                                                                                                                                                                                                                                                                                      |
| _requires_conversation_resolution_ | boolean                                |                                                                                              |                                                                                                                                                                                                                                                                                                                      |
| _requires_linear_history_          | boolean                                | If merge commits are prohibited from being pushed to this branch                             |                                                                                                                                                                                                                                                                                                                      |
| _requires_status_checks_           | boolean                                | TBD                                                                                          |                                                                                                                                                                                                                                                                                                                      |
| _required_status_checks_           | list\[[StatusCheck](status-check.md)\] | List of status checks that must pass before branches can be merged                           |                                                                                                                                                                                                                                                                                                                      |
| _requires_strict_status_checks_    | boolean                                | TBD                                                                                          |                                                                                                                                                                                                                                                                                                                      |
| _restricts_review_dismissals_      | boolean                                | If only allowed actors can dismiss reviews on pull requests                                  |                                                                                                                                                                                                                                                                                                                      |
| _review_dismissal_allowances_      | list\[[Actor](actor.md)\]              | List of actors that are permitted to dismiss reviews on pull requests                        |                                                                                                                                                                                                                                                                                                                      |
| _requires_deployments_             | boolean                                |                                                                                              |                                                                                                                                                                                                                                                                                                                      |
| _required_deployment_environments_ | list[string]                           |                                                                                              |                                                                                                                                                                                                                                                                                                                      |


Note:

* `allows_force_pushes`: if this set to `True`, any actor with push permission can force push to the branch
* `bypass_force_push_allowances`: if the actor list is non-empty but `allows_force_pushes` is set to True, a validation error will be issued
* `push_restrictions`: the contents of the actor list controls whether push restriction is enabled or disabled, i.e. an empty list disables it
* `review_dismissal_allowances`: if the actor list is non-empty but `restricts_review_dismissals` is set to False, a validation error will be issued

## Jsonnet Function

``` jsonnet
orgs.newBranchProtectionRule('<pattern>') {
  <key>: <value>
}
```

## Validation rules

- TODO

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('adoptium') {
      ...
      _repositories+:: [
        ...
        orgs.newRepo('adoptium.net') {
          description: "Adoptium Website",
          homepage: "https://adoptium.net",
          branch_protection_rules: [
            orgs.newBranchProtectionRule('main') {
              required_approving_review_count: 1,
              required_status_checks+: [
                "Lint Code Base",
                "Run CI",
                "netlify:netlify/eclipsefdn-adoptium/deploy-preview"
              ],
            },
          ],
        },
      ],
    }
    ```
