| Field                                                    | Type            | Description                                                                                     | Comment           |
|----------------------------------------------------------|-----------------|-------------------------------------------------------------------------------------------------|-------------------|
| name                                                     | string or null  | Name of the organization                                                                        |                   |
| billing_email                                            | string          | Billing email                                                                                   |                   |
| company                                                  | string or null  | Company name                                                                                    |                   |
| email                                                    | string or null  | Main contact point of the organization                                                          |                   |
| twitter_username                                         | string or null  | Twitter username                                                                                |                   |
| location                                                 | string or null  | Location                                                                                        |                   |
| description                                              | string or null  | Description                                                                                     |                   |
| blog                                                     | string or null  | Url of the blog                                                                                 |                   |
| plan                                                     | string          | Billing plan of the organization                                                                | read-only         |
| has_organization_projects                                | boolean         | If the organization can have projects                                                           |                   |
| has_repository_projects                                  | boolean         | If the organization has repository projects                                                     |                   |
| default_repository_permission                            | string          | Default repository permissions                                                                  |                   |
| members_can_create_private_repositories                  | boolean         | If members can create private repos                                                             |                   |
| members_can_create_public_repositories                   | boolean         | If members can create public repos                                                              |                   |
| members_can_fork_private_repositories                    | boolean         | If members can fork private repos                                                               |                   |
| web_commit_signoff_required                              | boolean         | If web commit signoff is required                                                               |                   |
| members_can_create_pages                                 | boolean         | If members can create pages                                                                     |                   |
| members_can_create_public_pages                          | boolean         | If members can create public pages                                                              |                   |
| dependabot_alerts_enabled_for_new_repositories           | boolean         | If dependabot alerts are enabled for new repos                                                  |                   |
| dependabot_security_updates_enabled_for_new_repositories | boolean         | If dependabot security updates are enabled for new repos                                        |                   |
| dependency_graph_enabled_for_new_repositories            | boolean         | If dependency graph is enabled for new repos                                                    |                   |
| members_can_change_repo_visibility                       | boolean         | If members can change repo visibility                                                           |                   |
| members_can_delete_repositories                          | boolean         | If members can delete repos                                                                     |                   |
| members_can_delete_issues                                | boolean         | If members can delete issues                                                                    |                   |
| readers_can_create_discussions                           | boolean or null | If readers can create discussions                                                               |                   |
| members_can_create_teams                                 | boolean         | If members can create teams                                                                     |                   |
| two_factor_requirement                                   | boolean         | If two factor is required for all members                                                       | read-only         |
| default_branch_name                                      | string          | The default branch name for repos                                                               |                   |
| packages_containers_public                               | boolean         | If members can push public releases / containers                                                |                   |
| packages_containers_internal                             | boolean         | If members can push private releases / containers                                               |                   |
| organization_projects_enabled                            | boolean         | If members can create organization projects                                                     |                   |
| members_can_change_project_visibility                    | boolean         | If members can change visibility of organization projects                                       |                   |
| default_workflow_permissions                             | string          | The default permissions granted to the GITHUB_TOKEN when running workflows in this organization | "read" or "write" |
| security_managers                                        | list[string]    | List of teams that should act as security managers                                              |                   |
