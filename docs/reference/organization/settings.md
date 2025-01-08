The following table captures all supported settings on organization level:

| Key                                             | Value                                        | Description                                                                                                                                                                    | Notes                                                  |
|-------------------------------------------------|----------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------|
| _name_                                          | string or null                               | The display name of the organization                                                                                                                                           |                                                        |
| _description_                                   | string or null                               | The description of the organization                                                                                                                                            |                                                        |
| _plan_                                          | string                                       | The billing plan of the organization                                                                                                                                           | read-only property                                     |
| _email_                                         | string or null                               | The main contact point of the organization                                                                                                                                     |                                                        |
| _billing_email_                                 | string                                       | The billing email                                                                                                                                                              |                                                        |
| _blog_                                          | string or null                               | The blog url (usually links to the homepage of the organization)                                                                                                               |                                                        |
| _twitter_username_                              | string or null                               | The twitter username of the organization                                                                                                                                       |                                                        |
| _location_                                      | string or null                               | The geographic location of the organization                                                                                                                                    |                                                        |
| _company_                                       | string or null                               | The company name if                                                                                                                                                            |                                                        |
| _default_branch_name_                           | string                                       | The default branch name for newly created repositories                                                                                                                         |                                                        |
| _default_repository_permission_                 | string                                       | The base permission for all members of the organization for its repositories                                                                                                   | `none`, `read`, `write` or `admin`                     |
| _default_code_security_configurations_disabled_ | boolean                                      | If default code security configuration should be disabled, no processing if the setting is set to `true`                                                                       |                                                        |
| _discussion_source_repository_                  | string or null                               | The source repository to host organization discussions                                                                                                                         |                                                        |
| _has_discussions_                               | boolean                                      | If discussions are enabled for the organization. If `true`, property `discussion_source_repository` must be set as well                                                        |                                                        |
| _has_organization_projects_                     | boolean                                      | If the organization can have organization projects                                                                                                                             |                                                        |
| _has_repository_projects_                       | boolean                                      | If the repositories can have repository projects                                                                                                                               |                                                        |
| _members_can_change_project_visibility_         | boolean                                      | If members with admin permissions for a project can change its visibility                                                                                                      |                                                        |
| _members_can_change_repo_visibility_            | boolean                                      | If members with admin permissions for a repo can change its visibility                                                                                                         |                                                        |
| _members_can_create_private_repositories_       | boolean                                      | If members can create private repos                                                                                                                                            |                                                        |
| _members_can_create_public_pages_               | boolean                                      | If members can create public GitHub Pages sites in this organization. If disabled, no GitHub Pages will not be published for the organization.                                 |                                                        |
| _members_can_create_public_repositories_        | boolean                                      | If members can create public repos                                                                                                                                             |                                                        |
| _members_can_create_teams_                      | boolean                                      | If members can create new teams                                                                                                                                                |                                                        |
| _members_can_delete_issues_                     | boolean                                      | If members with admin permissions for a repo can delete issues, otherwise only organization owners can delete issues                                                           |                                                        |
| _members_can_delete_repositories_               | boolean                                      | If members with admin permissions for a repo can delete or transfer it                                                                                                         |                                                        |
| _members_can_fork_private_repositories_         | boolean                                      | If members can fork private repos                                                                                                                                              |                                                        |
| _packages_containers_internal_                  | boolean                                      | If members can publish internal releases / containers visible to all organization members                                                                                      |                                                        |
| _packages_containers_public_                    | boolean                                      | If members can publish public releases / containers visible to anyone                                                                                                          |                                                        |
| _readers_can_create_discussions_                | boolean or null                              | If users with read access can create and comment on discussions                                                                                                                |                                                        |
| _security_managers_                             | list[string]                                 | List of teams that should act as security managers                                                                                                                             |                                                        |
| _two_factor_requirement_                        | boolean                                      | If two factor is required for all members                                                                                                                                      | read-only property, can only be changed via the Web UI |
| _web_commit_signoff_required_                   | boolean                                      | If repositories require contributors to sign-off on commits they make through GitHub's web interface. If enabled on organization level, it overrides the setting on repo level |                                                        |
| _custom_properties_                             | list\[[CustomProperty](custom-property.md)\] | Definition of custom properties                                                                                                                                                |                                                        |
| _workflows_                                     | [Workflow Settings](#workflow-settings)      | Workflow settings on organizational level                                                                                                                                      |                                                        |

## Embedded Models

### Workflow Settings

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

- enabling either `dependabot_alerts_enabled_for_new_repositories` or `dependabot_security_updates_enabled_for_new_repositories` also requires enabling `dependency_graph_enabled_for_new_repositories`
- enabling `dependabot_security_updates_enabled_for_new_repositories` also requires enabling `dependabot_alerts_enabled_for_new_repositories`
- enabling `has_discussions` also requires setting `discussion_source_repository` to a valid repository to host the discussions
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
            readers_can_create_discussions: true,
            security_managers+: [
                "adoptium-project-leads"
            ],
            twitter_username: "adoptium",
            web_commit_signoff_required: false,
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
