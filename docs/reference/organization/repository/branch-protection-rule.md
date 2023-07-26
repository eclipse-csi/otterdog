Definition of a Branch Protection Rule, the following properties are supported:

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