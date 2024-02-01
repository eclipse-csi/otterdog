Definition of workflow settings on organization level, the following properties are supported:

| Key                                        | Value        | Description                                                       | Notes                                                                    |
|--------------------------------------------|--------------|-------------------------------------------------------------------|--------------------------------------------------------------------------|
| _enabled_repositories_                     | string       | Defines which repositories are permitted to use GitHub Actions    | `all`, `none` or `selected`                                              |
| _selected_repositories_                    | list[string] | The list of repositories that are permitted to use GitHub Actions | Only taken into account when `enabled_repositories` is set to `selected` |
| _allowed_actions_                          | string       | Defines which type of GitHub Actions are permitted to run         | `all`, `local_only` or `selected`                                        |
| _allow_github_owned_actions_               | boolean      | If GitHub owned actions are permitted to run                      | Only taken into account when `allowed_actions` is set to `selected`      |
| _allow_verified_creator_actions_           | boolean      | If GitHub Actions from verified creators are permitted to run     | Only taken into account when `allowed_actions` is set to `selected`      |
| _allow_action_patterns_                    | list[string] | A list of action patterns permitted to run                        | Only taken into account when `allowed_actions` is set to `selected`      |
| _default_workflow_permissions_             | string       | The default workflow permissions granted to the GITHUB_TOKEN      | `read` or `write`                                                        |
| _actions_can_approve_pull_request_reviews_ | boolean      | If actions can approve and merge pull requests                    |                                                                          |

## Validation rules

- specifying a non-empty list of `selected_repositories` while `enabled_repositories` is not set to `selected`, triggers a warning
- specifying a non-empty list of `allow_action_patterns` while `allowed_actions` is not set to `selected`, triggers a warning


## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('adoptium') {
        settings+: {
            blog: "https://adoptium.net",
            default_repository_permission: "none",
            description: "The Adoptium Working Group ...",
            name: "Eclipse Adoptium",
            workflows+: {
              allowed_actions: "selected",
              allow_action_patterns: [
                "marocchino/sticky-pull-request-comment@*",
                "release-drafter/release-drafter@*"
              ]
            }
        },
        ...
    }
    ```
