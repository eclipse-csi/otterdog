Definition of a Repository Ruleset, the following properties are supported:

| Key                                 | Value                                  | Description                                                                                                                                                                              | Notes                                                                                                                             |
|-------------------------------------|----------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| _name_                              | string                                 | The name of this repository ruleset                                                                                                                                                      |                                                                                                                                   |
| _enforcement_                       | string                                 | The enforcement status of this ruleset                                                                                                                                                   | Possible values are `active`, `disabled` or `evaluate` (`evaluate` only available when enterprise billing is enabled)             |
| _bypass_actors_                     | list\[[BypassActor](bypass-actor.md)\] | List of actors able to bypass this ruleset                                                                                                                                               |                                                                                                                                   |
| _include_refs_                      | list\[[RefMatcher](ref-matcher.md)\]   | List of refs or patterns to include matching branches                                                                                                                                    |                                                                                                                                   |
| _exclude_refs_                      | list\[[RefMatcher](ref-matcher.md)\]   | List of refs or patterns to exclude matching branches                                                                                                                                    |                                                                                                                                   |
| _allows_creations_                  | boolean                                | If disabled, only allows users with bypass permission to create matching refs                                                                                                            | Only taken into account when `restricts_pushes` is enabled                                                                        |
| _allows_deletions_                  | boolean                                | If disabled, only allows users with bypass permission to delete matching refs                                                                                                            |                                                                                                                                   |
| _allows_updates_                    | boolean                                | If disabled, only allows users with bypass permission to push matching refs                                                                                                              | Only taken into account when `restricts_pushes` is enabled                                                                        |
| _allows_force_pushes_               | boolean                                | If disabled, only allows users with bypass permission to force push matching refs                                                                                                        | This property takes precedence over `bypass_force_push_allowances` if enabled, allowing all users with write access to force push |
| _requires_pull_request_             | boolean                                | If enabled, requires a pull request before merging. All commits must be made to a non-protected branch and submitted via a pull request before they can be merged into matching branches |                                                                                                                                   |
| _required_approving_review_count_   | integer or null                        | If specified, pull requests targeting a matching branch require a number of approvals and no changes requested before they can be merged.                                                | Only taken into account when `requires_pull_request` is enabled, should be set to null when `requires_pull_request` is disabled   |
| _dismisses_stale_reviews_           | boolean                                | If enabled, dismiss approved reviews automatically when a new commit is pushed                                                                                                           | Only taken into account when `requires_pull_request` is enabled                                                                   |
| _requires_code_owner_review_        | boolean                                | If enabled, require an approved review in pull requests including files with a designated code owner                                                                                     | Only taken into account when `requires_pull_request` is enabled                                                                   |
| _requires_last_push_approval_       | boolean                                | Whether the most recent push must be approved by someone other than the person who pushed it                                                                                             | Only taken into account when `requires_pull_request` is enabled                                                                   |
| _requires_review_thread_resolution_ | boolean                                | If enabled, all conversations on code must be resolved before a pull request can be merged into a matching branch                                                                        | Only taken into account when `requires_pull_request` is enabled                                                                   |
| _requires_status_checks_            | boolean                                | If enabled, status checks must pass before branches can be merged into a matching branch                                                                                                 |                                                                                                                                   |
| _requires_strict_status_checks_     | boolean                                | If enabled, pull requests targeting a matching branch must have been tested with the latest code.                                                                                        | This setting will not take effect unless at least one status check is enabled                                                     |
| _required_status_checks_            | list\[[StatusCheck](status-check.md)\] | List of status checks that must succeed before branches can be merged                                                                                                                    | Only taken into account when `requires_status_checks` is enabled                                                                  |
| _requires_commit_signatures_        | boolean                                | If enabled, commits pushed to matching branches must have verified signatures                                                                                                            |                                                                                                                                   |
| _requires_linear_history_           | boolean                                | If enabled, prevent merge commits from being pushed to matching branches                                                                                                                 |                                                                                                                                   |
| _requires_deployments_              | boolean                                | If enabled, environments must be successfully deployed to before branches can be merged into a matching branch                                                                           |                                                                                                                                   |
| _required_deployment_environments_  | list[string]                           | List of environments that must be successfully deployed to before branches can be merged                                                                                                 | Only taken into account when `requires_deployments` is enabled                                                                    |

## Jsonnet Function

``` jsonnet
orgs.newRepoRuleset('<name>') {
  <key>: <value>
}
```

## Validation rules

- setting `enforcement` to `evaluate` for an organization on a `free` plan triggers an error
- enabling a setting that is only taken into account when another setting is enabled, triggers a warning, e.g. `dismisses_stale_reviews` is only valid when `requires_pull_request` is enabled
- specifying an integer value for `required_approving_review_count` while `requires_pull_request` is disabled, triggers a warning, set it to `null` instead

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
          ...
          rulesets: [
            orgs.newRepoRuleset('main') {
              bypass_actors+: [
                "@adoptium/project-leads",
              ],
              include_refs+: [
                "~DEFAULT_BRANCH"
              ],
              required_approving_review_count: 0,
            },
          ],
        },
      ],
    }
    ```
