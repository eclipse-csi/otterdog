# Change Log

## [1.0.3] - 23/04/2025

### Fixed

 - Dependencies updates for otterdog
 - Minor development docs and build updates

## [1.0.2] - 23/04/2025

### Fixed

 - Fixed support for using common DNS in MongoDB URL configuration ([#417](https://github.com/eclipse-csi/otterdog/pull/417))

## [1.0.1] - 08/04/2025

### Fixed

- Fixed support for `actions` as code scanning language ([#411](https://github.com/eclipse-csi/otterdog/pull/411))
- Fixed coercion of `has_discussion` property in case the repository is the source of organization discussions.
- Fixed importing an organization that has multiple custom properties defined.
- Fixed updating organization teams with `local-apply` operation.


## [1.0.0] - 28/02/2025

### Changed

- Changed severity of validation messages wrt to missing 'github-pages' environments from WARNING to INFO.


## [0.11.0] - 20/02/2025

### Added

- Added policy `dependency_track_upload` to upload SBOM data from workflows to a dependency track instance.
- Added operations `list-blueprints` and `approve-blueprints` to list and approve remediation PRs created for specific organizations.
- Added support for teams.
- Use asyncer to speed up retrieval of live settings. ([#209](https://github.com/eclipse-csi/otterdog/issues/209))

### Changed

- Updated development environment to use `poetry` version `2.0.0` and changed license classifier to `EPL-2.0`. ([#328](https://github.com/eclipse-csi/otterdog/issues/328))
- Changes the `exclude_team` filter to not consider teams defined in the default config.
- Converted workflow related settings into an embedded model object.
- Included option `repo-filter` of diff related operations already when getting live data from GitHub to speed up execution.

### Fixed

- Fixed display of forced updates in `plan` operations.

## [0.10.0] - 20/12/2024

### Added

- Added support for organization roles.
- Added operation `check-token-permissions` to list all granted and missing scopes for the cli token.
- Added option to specify reviewers for blueprint type `append_configuration`.
- Added view for currently active remediation PRs for configured blueprints.

### Changed

- Adapted default template for GitHub organizations to take an additional parameter: project_name.
- Changed accessing security managers of an organization using the organization roles api. ([#365](https://github.com/eclipse-csi/otterdog/issues/365))
- Disabled adding automatic help comments for bot users creating a pull request in the config repo.
- Disabled checking of team membership for bot users creating a pull request in the config repo.

### Fixed

- Fixed displaying changes when settings `squash_merge_commit_title` and `squash_merge_commit_message` were changed at the same time.
- Prevented setting `private_vulnerability_reporting_enabled` for private repositories.
- Prevented wrapping of long texts when importing the configuration.


## [0.9.0] - 09/12/2024

### Added

- Added validation rules for `squash` and `merge` commit title and message settings of a repository.
- Added new blueprint `scorecard_integration` to integrate OSSF Scorecard evaluations. ([#345](https://github.com/eclipse-csi/otterdog/issues/345))
- Added new blueprint `append_configuration` to append configuration snippets depending on certain conditions.
- Added support for organization rulesets. ([#158](https://github.com/eclipse-csi/otterdog/issues/158))
- Added support for templates in `required-file` blueprints. ([#322](https://github.com/eclipse-csi/otterdog/issues/322))
- Added support for a `post-add-objects` hook in the default configuration that gets executed after resources have been added. ([#318](https://github.com/eclipse-csi/otterdog/issues/318))
- Added new blueprint `pin_workflow` to pin used GitHub actions in workflows.
- Added new blueprint `required_file` to create files in repositories.
- Added a new operation `list-advisories` to list GitHub Security Advisories for organizations.

### Changed

- Added raising an `InsufficientPermissionsException` if the token lacks required OAuth scopes for a specific endpoint. ([#126](https://github.com/eclipse-csi/otterdog/issues/126))
- Improved the check mechanism for blueprints by only checking a certain number each run and by taking the last check time into account.
- Improved the update mechanism when installing a new GitHub organization to only update the newly added organization. ([#349](https://github.com/eclipse-csi/otterdog/issues/349))
- Integrated existing logging with standard python logging facility.
- Utilized `rich` console formatting instead of low-level colorama styles.
- Improved processing when archiving repositories to process all other requested changes before archiving them. ([#134](https://github.com/eclipse-csi/otterdog/issues/134))
- Split up policies into policies and blueprint and added support for them in the UI
- Improved processing of organization settings `web_commit_signoff_required` and `actions_can_approve_pull_request_reviews` to force update the same settings on repo level as changes will be implicitly performed by GitHub.

### Fixed

- Fixed retrieval of setting `two_factor_requirement` which has been renamed to `two_factor_required` in the Web UI. ([#339](https://github.com/eclipse-csi/otterdog/issues/339))
- Fixed exclusion of settings that can only be accessed via the Web UI in the `local-apply` operation. ([#330](https://github.com/eclipse-csi/otterdog/issues/330))
- Fixed updating or deleting webhooks with wildcard patterns via the `local-apply` operation. ([#325](https://github.com/eclipse-csi/otterdog/issues/325))
- Fixed importing of `rulesets` due to missing handling of embedded model object `required_status_checks`.
- Changing setting `squash_merge_commit_message` also requires that setting `squash_merge_commit_title` is present in the payload sent to GitHub.


## [0.8.0] - 27/10/2024

### Added

- Added validation for setting `gh_pages_source_path` of a repository to check for allowed values.
- Added a playground and visualization of the default settings for a project to the dashboard. ([#293](https://github.com/eclipse-csi/otterdog/issues/293))
- Added support for overriding default settings in the `otterdog config` from a file `.otterdog-defaults.json`.
- Added support for setting `required_merge_queue` in repository rulesets. ([#282](https://github.com/eclipse-csi/otterdog/issues/282))
- Added support for setting `target` in repository rulesets.
- Added support for parameter `--repo-filter` for `plan` and `apply` operations. ([#275](https://github.com/eclipse-csi/otterdog/issues/275))
- Added support for tags for deployment policies in `environments`. ([#268](https://github.com/eclipse-csi/otterdog/issues/268))
- Added support for `custom properties`. ([#256](https://github.com/eclipse-csi/otterdog/issues/256))
- Added validation for setting `forked_repository` of a repository to match the expected format `<owner>/<repo>`.
- Added operation `review-permissions` to review requested permissions updates from GitHub apps for an organization. ([#260](https://github.com/eclipse-csi/otterdog/issues/260))
- Added operation `uninstall-app` to uninstall a GitHub app for an organization.
- Added operation `local-apply` to apply change based on two local configurations. ([#257](https://github.com/eclipse-csi/otterdog/issues/257))
- Added policy `macos_large_runners` to control whether MacOS large runners are permitted to use in an organization. ([#251](https://github.com/eclipse-csi/otterdog/issues/251))
- Added operation `install-app` to install a GitHub app for an organization. ([#250](https://github.com/eclipse-csi/otterdog/issues/250))
- Added option `--no-diff` and `--force` to the `push-config` operation to disable showing diffs and interactive approvals. ([#246](https://github.com/eclipse-csi/otterdog/issues/246))

### Changed

- Do not include settings whose values is `null` in the plan operation output when a resource is added.
- Include `model_only` settings in the plan operation output when a resource is added.
- Converted status check related settings of a Ruleset into an embedded model object similar to merge queue settings.
- Display changes in list properties using sequence comparison.
- Converted pull request related settings of a Ruleset into an embedded model object similar to merge queue settings.
- Use `jsonata` instead of `jq` for querying json objects.
- Use `ghproxy` by default as transparent cache / proxy when accessing the GitHub API from the webapp. ([#274](https://github.com/eclipse-csi/otterdog/issues/274))
- Changed parameter `--update-filter` for various operations from a python regular expression to a shell pattern format.
- Changed operation `import` to mask webhook urls in a similar way as in the previous configuration if present.
- Added a retry logic for calls to `https://api.github.com` to gracefully handle intermittent connection problems.
- Changed `ApplyChangesTask` to use a `local-apply` operation rather than an `apply` operation. ([#257](https://github.com/eclipse-csi/otterdog/issues/257))
- Changed operation `fetch-config` to include 2 additional parameters `suffix` and `ref` to fetch a config from a specific git reference.
- Changed operation `push-config` to always show a diff of the local changes compared to the current remote configuration prior to execution. ([#246](https://github.com/eclipse-csi/otterdog/issues/246))

### Fixed

- Fixed throttling of comments generated when checking if the configuration is in sync with the live settings.
- Fixed creation of a `Ruleset` if no merge queue is specified.
- Ensured that validation for a `Ruleset` fails if any parameter of `required_pull_request` is missing as they are required.
- Creating a repo with `gh_pages_build_type: "disabled"` is now working again after changes on GitHub side.
- Avoided unnecessary GitHub API calls when getting the `default_branch` or `id` of a repository.
- Detect errors during an automatic `apply` operation and add a corresponding comment to the pull request.
- Support showing dialog windows when using operation `web-login`.
- Fixed showing changes to dummy secret values when performing a `local-plan` operation. ([#245](https://github.com/eclipse-csi/otterdog/issues/245))
- Added proper error handling in case no base_template is defined in the otterdog configuration file. ([#247](https://github.com/eclipse-csi/otterdog/issues/247))


## [0.7.0] - 10/06/2024

### Added

- Added support for disabling default code security configurations. ([#234](https://github.com/eclipse-csi/otterdog/issues/234))
- Added support for configuring default code scanning setup of a repository. ([#198](https://github.com/eclipse-csi/otterdog/issues/198))
- Added operation `open-pr` to automatically create a PR for local changes. ([#230](https://github.com/eclipse-csi/otterdog/issues/230))
- Added author information from git when pushing config changes with `push-config`. ([#228](https://github.com/eclipse-csi/otterdog/issues/228))

### Changed

- Deprecated organization settings `dependabot_alerts_enabled_for_new_repositories`,
  `dependabot_security_updates_enabled_for_new_repositories` and `dependency_graph_enabled_for_new_repositories`.
- Deprecated organization setting `has_repository_projects`.

### Fixed

- Fixed updating the configuration of a project when its base template changed. ([#221](https://github.com/eclipse-csi/otterdog/issues/221))
- Fixed updating configuration when the `github_id` of a project changed. ([#235](https://github.com/eclipse-csi/otterdog/issues/235))


## [0.6.0] - 24/04/2024

### Added

- Added support for oauth authentication using GitHub. ([#202](https://github.com/eclipse-csi/otterdog/issues/202))
- Added support for auto-merging of PRs under certain conditions. ([#110](https://github.com/eclipse-csi/otterdog/issues/110))
- Added handling for settings that require access to the Web UI. ([#208](https://github.com/eclipse-csi/otterdog/issues/208))
- Added support for repository setting `private_vulnerability_reporting_enabled`. ([#205](https://github.com/eclipse-csi/otterdog/issues/205))
- Added a graphql based query interface to the dashboard. ([#204](https://github.com/eclipse-csi/otterdog/issues/204))

### Changed

- Reduced the number of automatic checks that are performed every time a PR gets updated. ([#217](https://github.com/eclipse-csi/otterdog/issues/217))
- Support auto-merge also for project leads and admins. ([#216](https://github.com/eclipse-csi/otterdog/issues/216))
- Do not enable auto-merge for PRs that also touch files other than the configuration. ([#220](https://github.com/eclipse-csi/otterdog/issues/220))
- Use scoped commands for interaction via pull requests. ([#211](https://github.com/eclipse-csi/otterdog/issues/211))

### Fixed

- Use pagination when retrieving all branches of a repository.


## [0.5.0] - 05/03/2024

Note: this version includes lots of additions and changes related to the GitHub App mode which are not
covered in the changelog.

### Added

- Added automatic handling of configuration changes by acting as a GitHub App.
- Support adding wildcards to `Webhook` urls to hide sensitive parts. ([#84](https://github.com/eclipse-csi/otterdog/issues/84))

### Changed

- Removed `jsonnetfile.json` and `jsonnetfile.lock.json` files in the config repo.

## [0.4.0] - 31/01/2024

### Added

- Support running otterdog as a GitHub app. ([#16](https://github.com/eclipse-csi/otterdog/issues/16))
- Added operation `install-deps` in order to install required runtime dependencies (firefox browser).

### Changed

- Include changes to secret values in `Webhooks` and `Secret` resources in plan operations. ([#168](https://github.com/eclipse-csi/otterdog/issues/168))
- Improve coercing of organization-level settings for repository settings. ([#161](https://github.com/eclipse-csi/otterdog/issues/161))
- Coerce repository workflow settings from organization workflow settings that are more restrictive. ([#135](https://github.com/eclipse-csi/otterdog/issues/135))

### Fixed

- Correctly coerce workflow setting `actions_can_approve_pull_request_reviews` and add a validation rule. ([#166](https://github.com/eclipse-csi/otterdog/issues/166))


## [0.3.0] - 05/12/2023

### Added

- Added support for creating new repositories as fork. ([#153](https://github.com/eclipse-csi/otterdog/issues/153))
- Added support for action variables on organizational and repository level. ([#150](https://github.com/eclipse-csi/otterdog/issues/150))
- Added operation `list-members` to display the amount of members for an organization.
- Added support for repository rulesets. ([#53](https://github.com/eclipse-csi/otterdog/issues/53))
- Added support for workflow settings of a repository. ([#113](https://github.com/eclipse-csi/otterdog/issues/113))
- Added possibility to define custom hooks in the default configuration when adding new resource. ([#106](https://github.com/eclipse-csi/otterdog/issues/106))
- Added validation for repos hosting the organization site, i.e. <org-id>.github.io. ([#83](https://github.com/eclipse-csi/otterdog/issues/83))
- Added validation for secrets and webhooks to issue a warning if a value is provided that does not use a credential provider.
- Added operation `delete-file` to delete files in a repo of an organization.
- Added support for workflow settings for an organization. ([#62](https://github.com/eclipse-csi/otterdog/issues/62))
- Added operation `list-apps` to display current app installations for an organization. ([#101](https://github.com/eclipse-csi/otterdog/issues/101))
- Added validation for secrets to not start with restricted prefix "GITHUB_". ([#100](https://github.com/eclipse-csi/otterdog/issues/100))
- Added operation `dispatch-workflow` to dispatch a workflow in a specified repository.
- Added flag `--update-filter` for plan, local-plan and apply operations to only update matching webhooks / secrets. ([#90](https://github.com/eclipse-csi/otterdog/issues/90))
- Added support for `github-pages` configuration for a repository. ([#59](https://github.com/eclipse-csi/otterdog/issues/59))
- Added support for `blocks_creations` and `restricts_pushes` settings for a branch protection rule. ([#87](https://github.com/eclipse-csi/otterdog/issues/87))
- Added support for custom validation rules that are retrieved together with the default configuration.
- Added support for `dependabot_security_updates_enabled` setting for a repository. ([#69](https://github.com/eclipse-csi/otterdog/issues/69))
- Added support for configuring discussions on organization and repository level. ([#67](https://github.com/eclipse-csi/otterdog/issues/67))
- Added support for shell autocompletion. ([#65](https://github.com/eclipse-csi/otterdog/issues/65))

### Removed

- Removed organization setting `default_workflow_permissions` which is now part of the workflow settings.
- Removed organization setting `members_can_create_pages` which is a read-only setting.
- Removed organization setting `organization_projects_enabled` which encodes the same information as `has_organization_projects`.

### Changed

- Updated library `aiohttp-client-cache` to v0.10.0 to support conditional requests natively. ([#139](https://github.com/eclipse-csi/otterdog/issues/139))
- Support renaming the current `default_branch` if the new branch does not exist yet. ([#76](https://github.com/eclipse-csi/otterdog/issues/76))
- Use async io for to speed up retrieval of current resources from GitHub. ([#114](https://github.com/eclipse-csi/otterdog/issues/114))
- Changed Operation `canonical-diff` to ignore ordering of keys.
- Support setting a non-existing branch as source branch for GitHub Pages deployment. ([#96](https://github.com/eclipse-csi/otterdog/issues/96))
- Renamed branch protection rule property `required_approving_reviews` to `requires_pull_request` which is more consistent with its semantics.
- Exclude temporary private fork repositories created for security advisories. ([#66](https://github.com/eclipse-csi/otterdog/issues/66))
- Adding a retry mechanism for generating a totp when signing in via the GitHub Web UI due to a recent change that a totp can not be reused anymore.

### Fixed

- Apply repository workflow settings when creating a new repository. ([#130](https://github.com/eclipse-csi/otterdog/issues/130))
- Added validation for the maximum number of supported `topics` defined for a repository. ([#129](https://github.com/eclipse-csi/otterdog/issues/129))
- Prevent `sync-template` operation to fail in some cases due to cached responses. ([#125](https://github.com/eclipse-csi/otterdog/issues/125))
- Made creating of repositories from a template more resilient to errors. ([#124](https://github.com/eclipse-csi/otterdog/issues/124))
- Do not take `push_restrictions` into account for diff calculation when `restricts_pushes` is disabled. ([#121](https://github.com/eclipse-csi/otterdog/issues/121))
- Made retrieval of organization setting `readers_can_create_discussions` optional as it's not available for empty organizations. ([#116](https://github.com/eclipse-csi/otterdog/issues/116))
- Fixed resetting apply operation when running it on multiple organizations at the same time.
- Fixed retrieving repository secrets for temporary private clone repositories.

## [0.2.0] - 06/07/2023

### Added

- Added new operation `web-login` to open a browser window logged in to an organization.
- Added support for organization level `secrets`. ([#52](https://github.com/eclipse-csi/otterdog/issues/52))
- Added support for repository level `secrets`. ([#52](https://github.com/eclipse-csi/otterdog/issues/52))
- Added support for repository level `environments`. ([#58](https://github.com/eclipse-csi/otterdog/issues/58))
- Added new operation `show-live` to show the current live resources of an organization.
- Added support for changing the webhook url by introducing an additional field `aliases`.
- Added support for repository webhooks. ([#56](https://github.com/eclipse-csi/otterdog/issues/56))
- Added support for `requires_deployment` and `required_deployment_environment` settings for branch protection rules. ([#29](https://github.com/eclipse-csi/otterdog/issues/29))
- Added support for `auto_init` setting for repositories: when enabled, repositories will get initialized with a README.md upon creation.
- Added support to post process some content initialized from a template repo using setting `post_process_template_content`.
- Added support to delete resources that are missing in definition (must be explicitly enabled with flag `--delete-resources`). ([#49](https://github.com/eclipse-csi/otterdog/issues/49))
- Added support for renaming of repositories by introducing an additional field `aliases`. ([#43](https://github.com/eclipse-csi/otterdog/issues/43))
- Added support for overriding the `config_repo` setting per organization. ([#48](https://github.com/eclipse-csi/otterdog/issues/48))
- Added new operation `canonical-diff` to show differences of the current configuration compared to a canonical version. ([#45](https://github.com/eclipse-csi/otterdog/issues/45))
- Added new operation `sync-template` to synchronize the contents of repositories created from a template. ([#41](https://github.com/eclipse-csi/otterdog/issues/41))
- Added support for `topics` setting for repositories. ([#44](https://github.com/eclipse-csi/otterdog/issues/44))

### Changed

- Changed `import` operation to sync secrets from existing configurations.
- Changed format to specify actors in branch protection rules, using a '@' prefix to denote users and teams, and not prefix for apps.
- Deprecated setting `team_discussions_allowed` which has been removed from the GitHub Web UI. ([#54](https://github.com/eclipse-csi/otterdog/issues/54))
- Changed indentation for import operation.
- Skipping organization webhooks with a dummy secret during processing.
- Simplified setting `base_template` and support a per-organization override. ([#39](https://github.com/eclipse-csi/otterdog/issues/39))
- Operation `import` will create a backup of the existing definition for an organization if it already exists.
- Non-existing users and teams will now trigger a warning message rather a failure during the execution of an `apply` operation. ([#51](https://github.com/eclipse-csi/otterdog/issues/51))
- Prevent printing of credential data when trace mode is enabled. ([#47](https://github.com/eclipse-csi/otterdog/issues/47))
- Switching to module `click` for command line parsing.
- Updated module `playwright` to version 1.33.0.
- Updated module `requests` to version 2.30.0.

### Fixed

- Fixed selector for logging out a user when accessing the GitHub Web UI after some changes to the Web UI.


## [0.1.0] - 15/05/2023

### Added

- Added support for `default_workflow_permissions` setting for organizations. ([#36](https://github.com/eclipse-csi/otterdog/issues/36))
- Added support for `security_managers` setting for organizations. ([#35](https://github.com/eclipse-csi/otterdog/issues/35))
- Added support for `is_template` and `template_repository` setting for repository settings. ([#34](https://github.com/eclipse-csi/otterdog/issues/34))
- Added flag `--update-webhooks` for apply / plan / local-plan operations to force updates of webhooks with secrets. ([#21](https://github.com/eclipse-csi/otterdog/issues/21))
- Added support for `secret_scanning_push_protection` setting for repository settings. ([#33](https://github.com/eclipse-csi/otterdog/issues/33))
- Added support for extending list-based properties, e.g. `required_status_checks` for branch protection rules.
- Added operation `local-plan` to output changes that will be applied by based on another local config.
- Added flag `--pull-request` for fetch-config operation to fetch the config from a specific pull request.
- Added support for `required_status_checks` setting for branch protection rules. ([#5](https://github.com/eclipse-csi/otterdog/issues/5))
- Added flag `--message` for push-config operation to specify the commit message.
- Added support for pre-defined repositories in the default configuration. ([#23](https://github.com/eclipse-csi/otterdog/issues/23))
- Added option `--no-web-ui` for import operation as well. ([#20](https://github.com/eclipse-csi/otterdog/issues/20))
- Added request caching for REST api calls. ([#18](https://github.com/eclipse-csi/otterdog/issues/18))
- Added support for `bypass_force_push_allowances` setting for branch protection rules. ([#5](https://github.com/eclipse-csi/otterdog/issues/5))
- Added support for `bypass_pull_request_allowances` setting for branch protection rules. ([#5](https://github.com/eclipse-csi/otterdog/issues/5))
- Added support for `review_dismissal_allowances` setting for branch protection rules. ([#5](https://github.com/eclipse-csi/otterdog/issues/5))
- Added support for `push_restrictions` setting for branch protection rules. ([#5](https://github.com/eclipse-csi/otterdog/issues/5))
- Added option `--no-web-ui` to skip processing settings accessed via the GitHub Web UI. ([#12](https://github.com/eclipse-csi/otterdog/issues/12))

### Changed

- Changed settings for branch protection rules from camel case to snake case notation. ([#37](https://github.com/eclipse-csi/otterdog/issues/37))
- Removed prefix `organization_` from settings `organization_projects_enabled` and `members_can_change_project_visibility` for organizations. ([#38](https://github.com/eclipse-csi/otterdog/issues/38))
- Switch to go-jsonnet and use released version `v0.20.0` in the container image. ([#25](https://github.com/eclipse-csi/otterdog/issues/25))
- Use released version `v0.5.1` of `jsonnet-bundler` in the container image. ([#24](https://github.com/eclipse-csi/otterdog/issues/24))
- Update some repo settings after creation as they are not taken correctly into account during creation by GitHub.
- Added special handling for `web_commit_signoff_required`: if changed organization wide, it will implicitly change the same setting on repo level.
- Removed `restricts_pushes` setting from branch protection rules as it is implicitly set based on setting `push_restrictions`.
