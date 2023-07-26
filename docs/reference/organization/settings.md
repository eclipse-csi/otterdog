The following table captures all supported settings on organization level:

| Key                                                        | Value           | Description                                                                                                                                                                    | Notes                                                  |
|------------------------------------------------------------|-----------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------|
| _name_                                                     | string or null  | The display name of the organization                                                                                                                                           |                                                        |
| _description_                                              | string or null  | The description of the organization                                                                                                                                            |                                                        |
| _plan_                                                     | string          | The billing plan of the organization                                                                                                                                           | read-only property                                     |
| _email_                                                    | string or null  | The main contact point of the organization                                                                                                                                     |                                                        |
| _billing_email_                                            | string          | The billing email                                                                                                                                                              |                                                        |
| _blog_                                                     | string or null  | The blog url (usually links to the homepage of the organization)                                                                                                               |                                                        |
| _twitter_username_                                         | string or null  | The twitter username of the organization                                                                                                                                       |                                                        |
| _location_                                                 | string or null  | The geographic location of the organization                                                                                                                                    |                                                        |
| _company_                                                  | string or null  | The company name if                                                                                                                                                            |                                                        |
| _default_branch_name_                                      | string          | The default branch name for newly created repositories                                                                                                                         |                                                        |
| _default_repository_permission_                            | string          | The base permission for all members of the organization for its repositories                                                                                                   | `none`, `read`, `write` or `admin`                     |
| _default_workflow_permissions_                             | string          | The default permissions granted to the GITHUB_TOKEN when running workflows in this organization                                                                                | `read` or `write`                                      |
| _dependabot_alerts_enabled_for_new_repositories_           | boolean         | If dependabot alerts will be enabled by default for newly created repos                                                                                                        |                                                        |
| _dependabot_security_updates_enabled_for_new_repositories_ | boolean         | If dependabot security updates will be enabled by default for newly created repos                                                                                              |                                                        |
| _dependency_graph_enabled_for_new_repositories_            | boolean         | If the dependency graph is will be enabled by default for newly created repos                                                                                                  |                                                        |
| _discussion_source_repository_                             | string or null  | The source repository to host organization discussions                                                                                                                         |                                                        |
| _has_discussions_                                          | boolean         | If discussions are enabled for the organization. If `true`, property `discussion_source_repository` must be set as well                                                        |                                                        |
| _has_organization_projects_                                | boolean         | If the organization can have organization projects                                                                                                                             |                                                        |
| _has_repository_projects_                                  | boolean         | If the repositories can have repository projects                                                                                                                               |                                                        |
| _members_can_change_project_visibility_                    | boolean         | If members with admin permissions for a project can change its visibility                                                                                                      |                                                        |
| _members_can_change_repo_visibility_                       | boolean         | If members with admin permissions for a repo can change its visibility                                                                                                         |                                                        |
| _members_can_create_private_repositories_                  | boolean         | If members can create private repos                                                                                                                                            |                                                        |
| _members_can_create_public_pages_                          | boolean         | If members can create public GitHub Pages sites in this organization. If disabled, no GitHub Pages will not be published for the organization.                                 |                                                        |
| _members_can_create_public_repositories_                   | boolean         | If members can create public repos                                                                                                                                             |                                                        |
| _members_can_create_teams_                                 | boolean         | If members can create new teams                                                                                                                                                |                                                        |
| _members_can_delete_issues_                                | boolean         | If members with admin permissions for a repo can delete issues, otherwise only organization owners can delete issues                                                           |                                                        |
| _members_can_delete_repositories_                          | boolean         | If members with admin permissions for a repo can delete or transfer it                                                                                                         |                                                        |
| _members_can_fork_private_repositories_                    | boolean         | If members can fork private repos                                                                                                                                              |                                                        |
| _packages_containers_internal_                             | boolean         | If members can publish internal releases / containers visible to all organization members                                                                                      |                                                        |
| _packages_containers_public_                               | boolean         | If members can publish public releases / containers visible to anyone                                                                                                          |                                                        |
| _readers_can_create_discussions_                           | boolean or null | If users with read access can create and comment on discussions                                                                                                                |                                                        |
| _security_managers_                                        | list[string]    | List of teams that should act as security managers                                                                                                                             |                                                        |
| _two_factor_requirement_                                   | boolean         | If two factor is required for all members                                                                                                                                      | read-only property, can only be changed via the Web UI |
| _web_commit_signoff_required_                              | boolean         | If repositories require contributors to sign-off on commits they make through GitHub's web interface. If enabled on organization level, it overrides the setting on repo level |                                                        |

## Validation rules

- enabling either `dependabot_alerts_enabled_for_new_repositories` or `dependabot_security_updates_enabled_for_new_repositories` also requires enabling `dependency_graph_enabled_for_new_repositories`
- enabling `dependabot_security_updates_enabled_for_new_repositories` also requires enabling `dependabot_alerts_enabled_for_new_repositories`
- enabling `has_discussions` also requires setting `discussion_source_repository` to a valid repository to host the discussions

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('adoptium') {
        settings+: { 
            blog: "https://adoptium.net",
            default_repository_permission: "none",
            default_workflow_permissions: "write",
            description: "The Adoptium Working Group ...",
            name: "Eclipse Adoptium",
            readers_can_create_discussions: true,
            security_managers+: [
                "adoptium-project-leads"
            ],
            twitter_username: "adoptium",
            web_commit_signoff_required: false,
        },
        ...
    }
    ```
