# Repository

Definition of a Repository for a GitHub organization, the following properties are supported:

| Key                                       | Value                                                     | Description                                                                             | Notes                                                                                                                                                                           |
|-------------------------------------------|-----------------------------------------------------------|-----------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| _name_                                    | string                                                    | Name of the repository                                                                  |                                                                                                                                                                                 |
| _aliases_                                 | list[string]                                              | List of repository alias names, need to add previous name when renaming a repository    |                                                                                                                                                                                 |
| _description_                             | string or null                                            | Project description                                                                     |                                                                                                                                                                                 |
| _homepage_                                | string or null                                            | Link to the homepage                                                                    |                                                                                                                                                                                 |
| _topics_                                  | list[string]                                              | The list of topics of this repository                                                   |                                                                                                                                                                                 |
| _private_                                 | boolean                                                   | If the project is private                                                               |                                                                                                                                                                                 |
| _archived_                                | boolean                                                   | If the repo is archived                                                                 |                                                                                                                                                                                 |
| _allow_auto_merge_                        | boolean                                                   | If auto merges are permitted                                                            |                                                                                                                                                                                 |
| _allow_forking_                           | boolean                                                   | If the repo allows private forking                                                      |                                                                                                                                                                                 |
| _allow_merge_commit_                      | boolean                                                   | If merge commits are permitted                                                          |                                                                                                                                                                                 |
| _allow_rebase_merge_                      | boolean                                                   | If rebase merges are permitted                                                          |                                                                                                                                                                                 |
| _allow_squash_merge_                      | boolean                                                   | If squash merges are permitted                                                          |                                                                                                                                                                                 |
| _allow_update_branch_                     | boolean                                                   | If pull requests should suggest updates                                                 |                                                                                                                                                                                 |
| _auto_init_                               | boolean                                                   | If the repository shall be auto-initialized during creation                             | only considered during creation                                                                                                                                                 |
| _code_scanning_default_setup_enabled_     | boolean                                                   | If the repo has default code scanning enabled                                           |                                                                                                                                                                                 |
| _code_scanning_default_query_suite_       | string                                                    | The query suite to use for default code scanning                                        | `default` or `extended`, only taken into account when `code_scanning_default_setup_enabled` is set to true                                                                      |
| _code_scanning_default_languages_         | list[string]                                              | The folder from which GitHub Pages should be built                                      | `actions`, `c-cpp`, `csharp`, `go`, `java-kotlin`, `javascript-typescript`, `python`, `ruby` or `swift`, only taken into account when `code_scanning_default_setup_enabled` is set to true |
| _custom_properties_                       | dict\[string, string \| list\[string\]\]                  | The custom properties to set for this repository                                        |                                                                                                                                                                                 |
| _default_branch_                          | string                                                    | Name of the default branch                                                              |                                                                                                                                                                                 |
| _delete_branch_on_merge_                  | boolean                                                   | If branches shall automatically be deleted after a merge                                |                                                                                                                                                                                 |
| _dependabot_alerts_enabled_               | boolean                                                   | If the repo has dependabot alerts enabled                                               |                                                                                                                                                                                 |
| _dependabot_security_updates_enabled_     | boolean                                                   | If the repo has dependabot security updates enabled                                     |                                                                                                                                                                                 |
| _gh_pages_build_type_                     | string                                                    | If the repo has GitHub Pages enabled                                                    | `disabled`, `legacy` or `workflow`. Build-type `legacy` refers to building from a branch                                                                                        |
| _gh_pages_source_branch_                  | string or null                                            | The branch from which GitHub Pages should be built                                      | only taken into account when `gh_pages_build_type` is set to `legacy`                                                                                                           |
| _gh_pages_source_path_                    | string or null                                            | The folder from which GitHub Pages should be built                                      | only taken into account when `gh_pages_build_type` is set to `legacy`                                                                                                           |
| _has_discussions_                         | boolean                                                   | If the repo has discussions enabled                                                     |                                                                                                                                                                                 |
| _has_issues_                              | boolean                                                   | If the repo can have issues                                                             |                                                                                                                                                                                 |
| _has_projects_                            | boolean                                                   | If the repo can have projects                                                           |                                                                                                                                                                                 |
| _has_wiki_                                | boolean                                                   | If the repo has a wiki                                                                  |                                                                                                                                                                                 |
| _is_template_                             | boolean                                                   | If the repo is can be used as a template repository                                     |                                                                                                                                                                                 |
| _merge_commit_message_                    | string                                                    | Can be PR_BODY, PR_TITLE, or BLANK for a default merge commit message                   |                                                                                                                                                                                 |
| _merge_commit_title_                      | string                                                    | Can be PR_TITLE or MERGE_MESSAGE for a default merge commit title                       |                                                                                                                                                                                 |
| _post_process_template_content_           | list[string]                                              | A list of content paths in a template repository that shall be processed after creation | only considered during creation                                                                                                                                                 |
| _private_vulnerability_reporting_enabled_ | boolean                                                   | If the repo has private vulnerability reporting enabled                                 |                                                                                                                                                                                 |
| _secret_scanning_                         | string                                                    | If secret scanning is "enabled" or "disabled"                                           |                                                                                                                                                                                 |
| _secret_scanning_push_protection_         | string                                                    | If secret scanning push protection is "enabled" or "disabled"                           |                                                                                                                                                                                 |
| _squash_merge_commit_message_             | string                                                    | Can be PR_BODY, COMMIT_MESSAGES, or BLANK for a default squash merge commit message     |                                                                                                                                                                                 |
| _squash_merge_commit_title_               | string                                                    | Can be PR_TITLE or COMMIT_OR_PR_TITLE for a default squash merge commit title           |                                                                                                                                                                                 |
| _template_repository_                     | string or null                                            | The template repository to use when creating the repo                                   | read-only, only considered during creation                                                                                                                                      |
| _forked_repository_                       | string or null                                            | The repository to fork when creating the repo                                           | only considered during creation                                                                                                                                                 |
| _fork_default_branch_only_                | boolean                                                   | When creating a fork, whether only the default branch will be included in the fork      | only considered during creation                                                                                                                                                 |
| _web_commit_signoff_required_             | boolean                                                   | If the repo requires web commit signoff                                                 |                                                                                                                                                                                 |
| _workflows_                               | [Workflow Settings](#workflow-settings)                   | Workflow settings on organizational level                                               |                                                                                                                                                                                 |
| _webhooks_                                | list\[[Webhook](webhook.md)\]                             | webhooks defined for this repo, see section above for details                           |                                                                                                                                                                                 |
| _secrets_                                 | list\[[RepositorySecret](secret.md)\]                     | secrets defined for this repo, see section below for details                            |                                                                                                                                                                                 |
| _variables_                               | list\[[RepositoryVariable](variable.md)\]                 | variables defined for this repo, see section below for details                          |                                                                                                                                                                                 |
| _environments_                            | list\[[Environment](environment.md)\]                     | environments defined for this repo, see section below for details                       |                                                                                                                                                                                 |
| _branch_protection_rules_                 | list\[[BranchProtectionRule](branch-protection-rule.md)\] | branch protection rules of the repo, see section below for details                      |                                                                                                                                                                                 |

## Embedded Models

### Workflow Settings

| Key                                        | Value        | Description                                                    | Notes                                                               |
|--------------------------------------------|--------------|----------------------------------------------------------------|---------------------------------------------------------------------|
| _enabled_                                  | boolean      | If GitHub actions are enabled for this repository              |                                                                     |
| _allowed_actions_                          | string       | Defines which type of GitHub Actions are permitted to run      | `all`, `local_only` or `selected`                                   |
| _allow_github_owned_actions_               | boolean      | If GitHub owned actions are permitted to run                   | Only taken into account when `allowed_actions` is set to `selected` |
| _allow_verified_creator_actions_           | boolean      | If GitHub Actions from verified creators are permitted to run  | Only taken into account when `allowed_actions` is set to `selected` |
| _allow_action_patterns_                    | list[string] | A list of action patterns permitted to run                     | Only taken into account when `allowed_actions` is set to `selected` |
| _default_workflow_permissions_             | string       | The default workflow permissions granted to the GITHUB_TOKEN   | `read` or `write`                                                   |
| _actions_can_approve_pull_request_reviews_ | boolean      | If actions can approve and merge pull requests                 |                                                                     |

## Jsonnet Function

=== "new"
    ``` jsonnet
    orgs.newRepo('<name>') {
      <key>: <value>
    }
    ```

=== "extend"
    ``` jsonnet
    orgs.extendRepo('<name>') {
      <key>: <value>
    }
    ```

!!! note

    In general, you will only ever use `orgs.newRepo` as this function will define a new repository with default
    values. However, in some cases it might be needed to change properties for a repo that has already been defined
    in the default configuration. In such situation, you should use `orgs.extendRepo`.

## Validation rules

- TODO: complete

- specifying a description of more than 350 characters triggers an error (maximum supported length by GitHub)
- specifying more than 20 topics triggers an error (maximum number of supported topics by GitHub)
- disabling `has_discussions` while this repository is configured as source repository for discussion of this organization triggers an error
- specifying a `template_repository` and `forked_repository` at the same time triggers an error
- specifying a non-empty list of `allow_action_patterns` while `allowed_actions` is not set to `selected`, triggers a warning

!!! tip

    Changing the default branch of a repository has the same behavior as doing it via the Web UI. If the new branch
    already exists, the default branch will be switched, otherwise, the current default branch will be renamed to the
    newly specified name.

!!! note

    When enabling GitHub Pages by setting `gh_pages_build_type` to either `legacy` or `workflow`, you should also
    define a `github-pages` environment, as it will be created automatically by GitHub.

!!! warning

    Specifying a code scanning language that is not detected by GitHub in the repo itself will lead to an error during applying.
    In general, default setup for code scanning should be used with care as it has some weird behavior, using a custom workflow
    is the preferred way to use CodeQL. For the custom workflow to succeed, you need to disable the default setup though.

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('adoptium') {
      ...
      _repositories+:: [
        ...
        orgs.newRepo('.github') {
          allow_auto_merge: true,
          allow_merge_commit: false,
          allow_update_branch: false,
          dependabot_alerts_enabled: false,
          web_commit_signoff_required: false,
          workflows+: {
            enabled: false,
          },
          branch_protection_rules: [
            orgs.newBranchProtectionRule('main'),
          ],
        },
    }
    ```
