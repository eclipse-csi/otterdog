# Change Log

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
