Definition of an `Organization Ruleset`, the following properties are supported:

| Key                                | Value                                                              | Description                                                                                                                                                                                | Notes                                                                                                                           |
|------------------------------------|--------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|
| _include_repo_names_               | list\[[RepoNameMatcher](repo-name-matcher.md)\]                    | List of names or patterns to include matching repositories                                                                                                                                 |                                                                                                                                 |
| _exclude_repo_names_               | list\[[RepoNameMatcher](repo-name-matcher.md)\]                    | List of names or patterns to exclude matching repositories                                                                                                                                 |                                                                                                                                 |
| _protect_repo_names_               | boolean                                                            | If enabled, target repositories can only be renamed by those with bypass permission                                                                                                        |                                                                                                                                 |
| _name_                             | string                                                             | The name of this repository ruleset                                                                                                                                                        |                                                                                                                                 |
| _target_                           | string                                                             | The target of this ruleset                                                                                                                                                                 | Possible values are `branch`, `tag` or `push`                                                                                   |
| _enforcement_                      | string                                                             | The enforcement status of this ruleset                                                                                                                                                     | Possible values are `active`, `disabled` or `evaluate` (`evaluate` only available when enterprise billing is enabled)           |
| _bypass_actors_                    | list\[[BypassActor](repository/bypass-actor.md)\]                  | List of actors able to bypass this ruleset                                                                                                                                                 |                                                                                                                                 |
| _include_refs_                     | list\[[RefMatcher](repository/ref-matcher.md)\]                    | List of refs or patterns to include matching branches                                                                                                                                      |                                                                                                                                 |
| _exclude_refs_                     | list\[[RefMatcher](repository/ref-matcher.md)\]                    | List of refs or patterns to exclude matching branches                                                                                                                                      |                                                                                                                                 |
| _allows_creations_                 | boolean                                                            | If disabled, only allows users with bypass permission to create matching refs                                                                                                              |                                                                                                                                 |
| _allows_deletions_                 | boolean                                                            | If disabled, only allows users with bypass permission to delete matching refs                                                                                                              |                                                                                                                                 |
| _allows_updates_                   | boolean                                                            | If disabled, only allows users with bypass permission to push matching refs                                                                                                                |                                                                                                                                 |
| _allows_force_pushes_              | boolean                                                            | If disabled, only allows users with bypass permission to force push matching refs                                                                                                          |                                                                                                                                 |
| _required_status_checks_           | [StatusCheckSettings](#status-check-settings) or null              | If specified, status checks must pass before branches can be merged into a matching branch                                                                                                 |                                                                                                                                 |
| _requires_commit_signatures_       | boolean                                                            | If enabled, commits pushed to matching branches must have verified signatures                                                                                                              |                                                                                                                                 |
| _requires_linear_history_          | boolean                                                            | If enabled, prevent merge commits from being pushed to matching branches                                                                                                                   |                                                                                                                                 |
| _requires_deployments_             | boolean                                                            | If enabled, environments must be successfully deployed to before branches can be merged into a matching branch                                                                             |                                                                                                                                 |
| _required_deployment_environments_ | list[string]                                                       | List of environments that must be successfully deployed to before branches can be merged                                                                                                   | Only taken into account when `requires_deployments` is enabled                                                                  |
| _required_pull_request_            | [PullRequestSettings](#pull-request-settings) or null              | If specified, requires a pull request before merging. All commits must be made to a non-protected branch and submitted via a pull request before they can be merged into matching branches |                                                                                                                                 |
| _required_merge_queue_             | [MergeQueueSettings](#merge-queue-settings) or null                | If specified, merges must be performed via a merge queue                                                                                                                                   |                                                                                                                                 |
| _copilot_code_review_              | [CopilotCodeReviewSettings](#copilot-code-review-settings) or null | If specified, request a review from Copilot automatically for new pull requests, if their author has access to Copilot code review                                                         | Not supported by rulesets with target `push`                                                                                    |
| _commit_message_pattern_           | [PatternSettings](#pattern-settings) or null                       | If specified, the message of the commits pushed to matching refs must match a pattern                                                                                                      | Not supported by rulesets with target `push`                                                                                    |
| _commit_author_email_pattern_      | [PatternSettings](#pattern-settings) or null                       | If specified, the email of the author of the commits pushed to matching refs must match a pattern                                                                                          | Not supported by rulesets with target `push`                                                                                    |
| _committer_email_pattern_          | [PatternSettings](#pattern-settings) or null                       | If specified, the email of the committer of the commits pushed to matching refs must match a pattern                                                                                       | Not supported by rulesets with target `push`                                                                                    |
| _branch_name_pattern_              | [PatternSettings](#pattern-settings) or null                       | If specified, the names of matching branches must match a pattern                                                                                                                          | Only supported by rulesets with target `branch`                                                                                 |
| _tag_name_pattern_                 | [PatternSettings](#pattern-settings) or null                       | If specified, the names of matching tags must match a pattern                                                                                                                              | Only supported by rulesets with target `tag`                                                                                    |
| _restricted_file_paths_            | list[string]                                                       | List of file paths that can not be pushed, using `fnmatch` syntax, e.g. `secrets/**`                                                                                                       | Only supported by rulesets with target `push`, at most 200 entries of up to 200 characters                                      |
| _restricted_file_paths_exceptions_ | list[string]                                                       | List of file paths that can be pushed even if they match `restricted_file_paths`                                                                                                           | Only taken into account when `restricted_file_paths` is not empty                                                               |
| _max_file_path_length_             | integer                                                            | The maximum number of characters of the paths of the files that can be pushed                                                                                                              | Only supported by rulesets with target `push`, allowed values in the range [0, 32767], `0` disables the rule                    |
| _restricted_file_extensions_       | list[string]                                                       | List of file extensions that can not be pushed, e.g. `*.exe`                                                                                                                               | Only supported by rulesets with target `push`, at most 200 entries of up to 200 characters                                      |
| _max_file_size_                    | integer                                                            | The maximum size in megabytes of the files that can be pushed, files stored with Git LFS are not limited                                                                                   | Only supported by rulesets with target `push`, allowed values in the range [0, 100], `0` disables the rule                      |
| _max_file_size_exceptions_         | list[string]                                                       | List of file paths that can exceed `max_file_size`                                                                                                                                         | Only taken into account when `max_file_size` is not `0`                                                                         |
| _required_code_scanning_           | [CodeScanningSettings](#code-scanning-settings) or null            | If specified, code scanning tools must provide results before branches can be merged into a matching branch                                                                                | Not supported by rulesets with target `push`                                                                                    |
| _required_workflows_               | [WorkflowsSettings](#workflows-settings) or null                   | If specified, workflows must pass before branches can be merged into a matching branch                                                                                                     | Not supported by rulesets with target `push`                                                                                    |

Rulesets support use-cases that can not be modelled with Branch Protection Rules, e.g. bypass actors that are
exempted from all rules of a ruleset, while the bypass allowances of a Branch Protection Rule only lift the pull
request requirement and required status checks still apply. See
[Rulesets or branch protection rules](../../userguide/guides/rulesets-vs-branch-protection.md) for a comparison and the
features of rulesets that are not supported, and [Protecting branches](../../userguide/guides/branch-protection.md) for
examples.

## Jsonnet Function

``` jsonnet
orgs.newOrgRuleset('<name>') {
  <key>: <value>
}
```

## Embedded Models

### Status Check Settings

| Key                        | Value                                             | Description                                                                                      | Notes                                                                         |
|----------------------------|---------------------------------------------------|--------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| _do_not_enforce_on_create_ | boolean                                           | If enabled, allow repositories and branches to be created if a check would otherwise prohibit it |                                                                               |
| _strict_                   | boolean                                           | If enabled, pull requests targeting a matching branch must have been tested with the latest code | This setting will not take effect unless at least one status check is enabled |
| _status_checks_            | list\[[StatusCheck](repository/status-check.md)\] | List of status checks that must succeed before branches can be merged                            |                                                                               |

#### Jsonnet Function

``` jsonnet
orgs.newStatusChecks() {
  <key>: <value>
}
```

### Pull Request Settings

| Key                                 | Value        | Description                                                                                                       | Notes                                                                                                                        |
|-------------------------------------|--------------|-------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| _required_approving_review_count_   | integer      | The number or approvals required before a pull request can be merged                                              | Allowed values in the range [0, 10]                                                                                          |
| _dismisses_stale_reviews_           | boolean      | If enabled, dismiss approved reviews automatically when a new commit is pushed                                    |                                                                                                                              |
| _requires_code_owner_review_        | boolean      | If enabled, require an approved review in pull requests including files with a designated code owner              |                                                                                                                              |
| _requires_last_push_approval_       | boolean      | Whether the most recent push must be approved by someone other than the person who pushed it                      |                                                                                                                              |
| _requires_review_thread_resolution_ | boolean      | If enabled, all conversations on code must be resolved before a pull request can be merged into a matching branch |                                                                                                                              |
| _allowed_merge_methods_             | list[string] | The merge methods that are allowed when merging a pull request into a matching branch                             | Allowed values: `merge`, `squash`, `rebase`; defaults to all three, matching GitHub's behavior when the parameter is omitted |

#### Jsonnet Function

``` jsonnet
orgs.newPullRequest() {
  <key>: <value>
}
```

### Merge Queue Settings

| Key                                                  | Value   | Description                                                                                                                                                                                                                                | Notes                                             |
|------------------------------------------------------|---------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------|
| _merge_method_                                       | string  | Method to use when merging changes from queued pull requests                                                                                                                                                                               | Possible values are `MERGE`, `SQUASH` or `REBASE` |
| _build_concurrency_                                  | integer | Limit the number of queued pull requests requesting checks and workflow runs at the same time                                                                                                                                              | Must be in non-negative number                    |
| _min_group_size_                                     | integer | The minimum number of PRs that will be merged together in a group                                                                                                                                                                          | Must be in non-negative number                    |
| _max_group_size_                                     | integer | The maximum number of PRs that will be merged together in a group                                                                                                                                                                          | Must be in non-negative number                    |
| _wait_time_for_minimum_group_size_                   | integer | The time in minutes the merge queue should wait after the first PR is added to the queue for the minimum group size to be met.<br/>After this time has elapsed, the minimum group size will be ignored and a smaller group will be merged  | Must be in non-negative number                    |
| _status_check_timeout_                               | integer | Maximum time in minutes for a required status check to report a conclusion.<br/>After this much time has elapsed, checks that have not reported a conclusion will be assumed to have failed                                                | Must be in non-negative number                    |
| _requires_all_group_entries_to_pass_required_checks_ | boolean | When this setting is disabled, only the commit at the head of the merge group, i.e. the commit containing changes from all of the PRs in the group, must pass its required checks to merge                                                 |                                                   |

#### Jsonnet Function

``` jsonnet
orgs.newMergeQueue() {
  <key>: <value>
}
```

### Copilot Code Review Settings

| Key                          | Value   | Description                                                                                | Notes |
|------------------------------|---------|--------------------------------------------------------------------------------------------|-------|
| _review_on_push_             | boolean | If enabled, Copilot reviews each new push to the pull request                              |       |
| _review_draft_pull_requests_ | boolean | If enabled, Copilot reviews draft pull requests before they are marked as ready for review |       |

#### Jsonnet Function

``` jsonnet
orgs.newCopilotCodeReview() {
  <key>: <value>
}
```

### Pattern Settings

| Key        | Value   | Description                                       | Notes                                                                 |
|------------|---------|---------------------------------------------------|-----------------------------------------------------------------------|
| _operator_ | string  | The operator used to match the pattern            | Possible values are `starts_with`, `ends_with`, `contains` or `regex` |
| _pattern_  | string  | The pattern to match                              | Must not be empty                                                     |
| _name_     | string  | The name of the rule shown on GitHub              | Not sent to GitHub if empty                                           |
| _negate_   | boolean | If enabled, the rule fails if the pattern matches |                                                                       |

#### Jsonnet Function

``` jsonnet
orgs.newPattern() {
  <key>: <value>
}
```

### Code Scanning Settings

| Key                   | Value        | Description                                                                                                                                            | Notes                                                                                                                                                                                                                        |
|-----------------------|--------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| _code_scanning_tools_ | list[string] | List of code scanning tools that must provide results, as `<tool>:<security_alerts_threshold>:<alerts_threshold>`, e.g. `CodeQL:high_or_higher:errors` | At least one tool must be listed. Possible security alerts thresholds are `none`, `critical`, `high_or_higher`, `medium_or_higher` or `all`, possible alerts thresholds are `none`, `errors`, `errors_and_warnings` or `all` |

#### Jsonnet Function

``` jsonnet
orgs.newCodeScanning() {
  <key>: <value>
}
```

### Workflows Settings

| Key                        | Value        | Description                                                                                                                                   | Notes                                                                            |
|----------------------------|--------------|-----------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| _do_not_enforce_on_create_ | boolean      | If enabled, allow repositories and branches to be created if a workflow would otherwise prohibit it                                           |                                                                                  |
| _workflows_                | list[string] | List of workflows that must pass, as `<owner>/<repository>:<path>[@<ref>]`, e.g. `my-org/.github:.github/workflows/build.yml@refs/heads/main` | At least one workflow must be listed. The ref is a branch, a tag or a commit sha |

#### Jsonnet Function

``` jsonnet
orgs.newWorkflows() {
  <key>: <value>
}
```

## Validation rules

- setting `enforcement` to `evaluate` for an organization on a non `enterprise` plan triggers an error
- setting `target` must be one of `branch`, `tag` or `push`, any other value triggers an error
- setting `restricted_file_paths`, `max_file_path_length`, `restricted_file_extensions` or `max_file_size` for a ruleset whose `target` is not `push` triggers an error
- setting a rule that rulesets with target `push` do not support, e.g. `copilot_code_review` or `commit_message_pattern`, for a ruleset with target `push` triggers an error, a warning for the rules `allows_*`, `requires_*`, `required_pull_request`, `required_status_checks` and `required_merge_queue`
- setting `branch_name_pattern` for a ruleset whose `target` is not `branch`, or `tag_name_pattern` for a ruleset whose `target` is not `tag` triggers an error
- setting `include_refs` or `exclude_refs` for a ruleset with target `push` triggers a warning, as push rulesets apply to all refs of a repository
- setting `max_file_path_length` outside the range [0, 32767], `max_file_size` outside the range [0, 100], or more than 200 entries or an entry longer than 200 characters in the lists of the push rules triggers an error
- setting `restricted_file_paths_exceptions` while `restricted_file_paths` is empty, or `max_file_size_exceptions` while `max_file_size` is `0` triggers a warning
- setting an invalid `operator`, an empty `pattern`, an invalid code scanning tool or threshold, an invalid code quality severity, a code coverage threshold outside the range [0, 100] or an invalid workflow triggers an error
- referencing the repository of a workflow by its id triggers an error, otterdog shows a repository by its id only if it can not resolve its name, e.g. if the repository was deleted
- setting a push rule, `required_code_quality` or `required_code_coverage` for an organization on a `free` plan triggers a warning, as they require at least GitHub Team
- setting a pattern, e.g. `commit_message_pattern`, or `requires_license_compliance_scanning` for an organization on a non `enterprise` plan triggers a warning, as they require GitHub Enterprise
- setting `required_code_quality`, `required_code_coverage` or `requires_license_compliance_scanning` triggers an error, as they are only supported by repository rulesets
- defining organization rulesets for an organization on a non `enterprise` plan triggers an error

## Example usage

The following ruleset would basically prevent force-pushes for the default branch of all repositories
of the `eclipse-csi` GitHub organization:

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('eclipse-csi') {
      ...
      rulesets: [
        orgs.newOrgRuleset('main') {
          include_repo_names: [
            "~ALL"
          ],
          include_refs+: [
            "~DEFAULT_BRANCH"
          ],
          required_pull_request: null,
          required_status_checks: null,
        },
      ],
    }
    ```
