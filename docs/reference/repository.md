---
hide:
  - toc
---

### Repository Settings

| Field                               | Type                         | Description                                                                             | Comment                         |
|-------------------------------------|------------------------------|-----------------------------------------------------------------------------------------|---------------------------------|
| name                                | string                       | Name of the repository                                                                  |                                 |
| aliases                             | list[string]                 | List of repository alias names, need to add previous name when renaming a repository    |                                 |
| description                         | string or null               | Project description                                                                     |                                 |
| homepage                            | string or null               | Link to the homepage                                                                    |                                 |
| private                             | boolean                      | If the project is private                                                               |                                 |
| has_discussions                     | boolean                      | If the repo has discussions enabled                                                     |                                 |
| has_issues                          | boolean                      | If the repo can have issues                                                             |                                 |
| has_projects                        | boolean                      | If the repo can have projects                                                           |                                 |
| has_wiki                            | boolean                      | If the repo has a wiki                                                                  |                                 |
| is_template                         | boolean                      | If the repo is can be used as a template repository                                     |                                 |
| topics                              | list[string]                 | The list of topics of this repository.                                                  |                                 |
| template_repository                 | string or null               | The template repository to use when creating the repo                                   | read-only                       |
| post_process_template_content       | list[string]                 | A list of content paths in a template repository that shall be processed after creation | only considered during creation | 
| auto_init                           | boolean                      | If the repository shall be auto-initialized during creation                             | only considered during creation |
| default_branch                      | string                       | Name of the default branch                                                              |                                 |
| allow_rebase_merge                  | boolean                      | If rebase merges are permitted                                                          |                                 |
| allow_merge_commit                  | boolean                      | If merge commits are permitted                                                          |                                 |
| allow_squash_merge                  | boolean                      | If squash merges are permitted                                                          |                                 |
| allow_auto_merge                    | boolean                      | If auto merges are permitted                                                            |                                 |
| delete_branch_on_merge              | boolean                      | If branches shall automatically be deleted after a merge                                |                                 |
| allow_update_branch                 | boolean                      | If pull requests should suggest updates                                                 |                                 |
| squash_merge_commit_title           | string                       | Can be PR_TITLE or COMMIT_OR_PR_TITLE for a default squash merge commit title           |                                 |
| squash_merge_commit_message         | string                       | Can be PR_BODY, COMMIT_MESSAGES, or BLANK for a default squash merge commit message     |                                 |
| merge_commit_title                  | string                       | Can be PR_TITLE or MERGE_MESSAGE for a default merge commit title                       |                                 |
| merge_commit_message                | string                       | Can be PR_BODY, PR_TITLE, or BLANK for a default merge commit message                   |                                 |
| archived                            | boolean                      | If the repo is archived                                                                 |                                 |
| allow_forking                       | boolean                      | If the repo allows private forking                                                      |                                 |
| web_commit_signoff_required         | boolean                      | If the repo requires web commit signoff                                                 |                                 |
| secret_scanning                     | string                       | If secret scanning is "enabled" or "disabled"                                           |                                 |
| secret_scanning_push_protection     | string                       | If secret scanning push protection is "enabled" or "disabled"                           |                                 |
| dependabot_alerts_enabled           | boolean                      | If the repo has dependabot alerts enabled                                               |                                 |
| dependabot_security_updates_enabled | boolean                      | If the repo has dependabot security updates enabled                                     |                                 |
| webhooks                            | list[webhook]                | webhooks defined for this repo, see section above for details                           |                                 |
| secrets                             | list[repo-secret]            | secrets defined for this repo, see section below for details                            |                                 |
| environments                        | list[environment]            | environments defined for this repo, see section below for details                       |                                 |
| branch_protection_rules             | list[branch-protection-rule] | branch protection rules of the repo, see section below for details                      |                                 |

### Repository Secrets

| Field                 | Type           | Description                                                                                 |
|-----------------------|----------------|---------------------------------------------------------------------------------------------|
| name                  | string         | The name of the secret                                                                      |
| value                 | string         | The secret value                                                                            |

The secret value can be resolved using a credential provider in the same way as for Webhooks.

### Environment

| Field                    | Type         | Description                                                                                                                      |
|--------------------------|--------------|----------------------------------------------------------------------------------------------------------------------------------|
| name                     | string       | The name of the environment                                                                                                      |
| wait_timer               | int          | The amount of time to wait before allowing deployments to proceed                                                                |
| reviewers                | list[actor]  | Users or Teams that may approve workflow runs that access this environment                                                       |
| deployment_branch_policy | string       | Limit which branches can deploy to this environment based on rules or naming patterns, can be `all` or `protected` or `selected` |
| branch_policies          | list[string] | List of branch patterns which can deploy to this environment, only used when `deployment_branch_policy` is set to `selected`     |

### Branch Protection Rules

| Field                           | Type              | Description                                                                                  |
|---------------------------------|-------------------|----------------------------------------------------------------------------------------------|
| pattern                         | string            | Pattern to match branches                                                                    |
| allows_deletions                | boolean           | If the branch can be deleted                                                                 |
| allows_force_pushes             | boolean           | If branch allows force pushes                                                                |
| bypass_force_push_allowances    | list[actor]       | List of actors able to force push for this branch protection rule                            |
| bypass_pull_request_allowances  | list[actor]       | List of actors able to bypass PRs for this branch protection rule                            |
| dismisses_stale_reviews         | boolean           | Dismiss approved reviews automatically when a new commit is pushed                           |
| is_admin_enforced               | boolean           | Enforces the branch protection rule for admins                                               |
| lock_allows_fetch_and_merge     | boolean           | If the repo has dependabot alerts enabled                                                    |
| lock_branch                     | boolean           | If the branch is read-only                                                                   |
| push_restrictions               | list[actor]       | List of actors that are permitted to push to the branch                                      |
| require_last_push_approval      | boolean           | Whether the most recent push must be approved by someone other than the person who pushed it |
| required_approving_review_count | integer or null   | TBD                                                                                          |
| requires_approving_reviews      | boolean           | TBD                                                                                          |
| requires_code_owner_reviews     | boolean           | If reviews from code owners are required to update matching branches                         |
| requires_commit_signatures      | boolean           | If commits are required to be signed                                                         |
| requires_linear_history         | boolean           | If merge commits are prohibited from being pushed to this branch                             |
| requires_status_checks          | boolean           | TBD                                                                                          |
| requires_strict_status_checks   | boolean           | TBD                                                                                          |
| restricts_review_dismissals     | boolean           | If only allowed actors can dismiss reviews on pull requests                                  |
| review_dismissal_allowances     | list[actor]       | List of actors that are permitted to dismiss reviews on pull requests                        |
| required_status_checks          | list[statuscheck] | List of status checks that must pass before branches can be merged                           |


Note:

* `allows_force_pushes`: if this set to `True`, any actor with push permission can force push to the branch
* `bypass_force_push_allowances`: if the actor list is non-empty but `allows_force_pushes` is set to True, a validation error will be issued
* `push_restrictions`: the contents of the actor list controls whether push restriction is enabled or disabled, i.e. an empty list disables it
* `review_dismissal_allowances`: if the actor list is non-empty but `restricts_review_dismissals` is set to False, a validation error will be issued

### Actor Format

* User: `@<user-login>`, e.g. `@netomi`
* Team: `@<team-combined-slug>`, the combined slug has the format `<organization>/<team-slug>`, e.g. `@OtterdogTest/committers`
* App: `<app-slug>`, e.g. `eclipse-eca-validation`

### Status Check Format

* GitHub Action Status: `<status-name>`, e.g. `Run CI`
* Status from an app: `<app-slug>:<status-name>`, e.g. `eclipse-eca-validation:eclipsefdn/eca`
* Status from any source: `any:<status-name`, e.g. `any:Run CI`