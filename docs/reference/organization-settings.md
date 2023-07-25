---
hide:
  - toc
---

Supported properties

| Key                                                        | Type            | Description                                                                                                             | Notes                              |
|------------------------------------------------------------|-----------------|-------------------------------------------------------------------------------------------------------------------------|------------------------------------|
| `billing_email`                                            | string          | The billing email                                                                                                       |                                    |
| `blog`                                                     | string or null  | The blog url (usually links to the homepage of the organization)                                                        |                                    |
| `company`                                                  | string or null  | The company name if                                                                                                     |                                    |
| `default_branch_name`                                      | string          | The default branch name for newly created repositories                                                                  |                                    |
| `default_repository_permission`                            | string          | The base permission for all members of the organization for its repositories                                            | "none", "read", "write" or "admin" |
| `default_workflow_permissions`                             | string          | The default permissions granted to the GITHUB_TOKEN when running workflows in this organization                         | "read" or "write"                  |
| `dependabot_alerts_enabled_for_new_repositories`           | boolean         | If dependabot alerts will be enabled by default for newly created repos                                                 |                                    |
| `dependabot_security_updates_enabled_for_new_repositories` | boolean         | If dependabot security updates will be enabled by default for newly created repos                                       |                                    |
| `dependency_graph_enabled_for_new_repositories`            | boolean         | If the dependency graph is will be enabled by default for newly created repos                                           |                                    |
| `description`                                              | string or null  | The description of the organization                                                                                     |                                    |
| `discussion_source_repository`                             | string or null  | The source repository to host organization discussions                                                                  |                                    |
| `email`                                                    | string or null  | The main contact point of the organization                                                                              |                                    |
| `has_discussions`                                          | boolean         | If discussions are enabled for the organization. If `true`, property `discussion_source_repository` must be set as well |                                    |
| `has_organization_projects`                                | boolean         | If the organization can have organization projects                                                                      |                                    |
| `has_repository_projects`                                  | boolean         | If the repositories can have repository projects                                                                        |                                    |
| `location`                                                 | string or null  | The geographic location of the organization                                                                             |                                    |
| `members_can_change_project_visibility`                    | boolean         | If members with admin permissions on a project can change its visibility                                                |                                    |
| `members_can_change_repo_visibility`                       | boolean         | If members with admin permissions on a repo can change its visibility                                                   |                                    |
| `members_can_create_private_repositories`                  | boolean         | If members can create private repos                                                                                     |                                    |
| `members_can_create_public_pages`                          | boolean         | If members can create public pages                                                                                      |                                    |
| `members_can_create_public_repositories`                   | boolean         | If members can create public repos                                                                                      |                                    |
| `members_can_create_teams`                                 | boolean         | If members can create teams                                                                                             |                                    |
| `members_can_delete_issues`                                | boolean         | If members can delete issues                                                                                            |                                    |
| `members_can_delete_repositories`                          | boolean         | If members can delete repos                                                                                             |                                    |
| `members_can_fork_private_repositories`                    | boolean         | If members can fork private repos                                                                                       |                                    |
| `name`                                                     | string or null  | The display name of the organization                                                                                    |                                    |
| `packages_containers_internal`                             | boolean         | If members can push private releases / containers                                                                       |                                    |
| `packages_containers_public`                               | boolean         | If members can push public releases / containers                                                                        |                                    |
| `plan`                                                     | string          | Billing plan of the organization                                                                                        | read-only                          |
| `readers_can_create_discussions`                           | boolean or null | If readers can create discussions                                                                                       |                                    |
| `security_managers`                                        | list[string]    | List of teams that should act as security managers                                                                      |                                    |
| `twitter_username`                                         | string or null  | Twitter username                                                                                                        |                                    |
| `two_factor_requirement`                                   | boolean         | If two factor is required for all members                                                                               | read-only                          |
| `web_commit_signoff_required`                              | boolean         | If web commit signoff is required                                                                                       |                                    |


Example

=== "jsonnet"
    ```jsonnet
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
    }
    ```
