# Change Log

## [0.2.0.dev] - unreleased

### Added

- Added support for `environments` for repositories. ([#58](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/58))
- Added new operation `show-live` to show the current live resources of an organization.
- Added support for changing the webhook url by introducing an additional field `aliases`.
- Added support for repository webhooks. ([#56](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/56))
- Added support for `requires_deployment` and `required_deployment_environment` settings for branch protection rules. ([#29](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/29))
- Added support for `auto_init` setting for repositories: when enabled, repositories will get initialized with a README.md upon creation.
- Added support to post process some content initialized from a template repo using setting `post_process_template_content`.
- Added support to delete resources that are missing in definition (must be explicitly enabled with flag `--delete-resources`). ([#49](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/49))
- Added support for renaming of repositories by introducing an additional field `aliases`. ([#43](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/43))
- Added support for overriding the `config_repo` setting per organization. ([#48](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/48))
- Added new operation `canonical-diff` to show differences of the current configuration compared to a canonical version. ([#45](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/45))
- Added new operation `sync-template` to synchronize the contents of repositories created from a template. ([#41](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/41))
- Added support for `topics` setting for repositories. ([#44](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/44))

### Changed

- Changed `import` operation to sync secrets from existing configurations.
- Changed format to specify actors in branch protection rules, using a '@' prefix to denote users and teams, and not prefix for apps.
- Deprecated setting `team_discussions_allowed` which has been removed from the GitHub Web UI. ([#54](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/54))
- Changed indentation for import operation.
- Skipping organization webhooks with a dummy secret during processing.
- Simplified setting `base_template` and support a per-organization override. ([#39](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/39))
- Operation `import` will create a backup of the existing definition for an organization if it already exists.
- Non-existing users and teams will now trigger a warning message rather a failure during the execution of an `apply` operation. ([#51](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/51))
- Prevent printing of credential data when trace mode is enabled. ([#47](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/47))
- Switching to module `click` for command line parsing.
- Updated module `playwright` to version 1.33.0.
- Updated module `requests` to version 2.30.0.

### Fixed

- Fixed selector for logging out a user when accessing the GitHub Web UI after some changes to the Web UI.


## [0.1.0] - 15/05/2023

### Added

- Added support for `default_workflow_permissions` setting for organizations. ([#36](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/36))
- Added support for `security_managers` setting for organizations. ([#35](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/35))
- Added support for `is_template` and `template_repository` setting for repository settings. ([#34](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/34))
- Added flag `--update-webhooks` for apply / plan / local-plan operations to force updates of webhooks with secrets. ([#21](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/21))
- Added support for `secret_scanning_push_protection` setting for repository settings. ([#33](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/33))
- Added support for extending list-based properties, e.g. `required_status_checks` for branch protection rules.
- Added operation `local-plan` to output changes that will be applied by based on another local config.
- Added flag `--pull-request` for fetch-config operation to fetch the config from a specific pull request.
- Added support for `required_status_checks` setting for branch protection rules. ([#5](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/5))
- Added flag `--message` for push-config operation to specify the commit message.
- Added support for pre-defined repositories in the default configuration. ([#23](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/23))
- Added option `--no-web-ui` for import operation as well. ([#20](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/20))
- Added request caching for REST api calls. ([#18](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/18))
- Added support for `bypass_force_push_allowances` setting for branch protection rules. ([#5](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/5))
- Added support for `bypass_pull_request_allowances` setting for branch protection rules. ([#5](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/5))
- Added support for `review_dismissal_allowances` setting for branch protection rules. ([#5](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/5))
- Added support for `push_restrictions` setting for branch protection rules. ([#5](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/5))
- Added option `--no-web-ui` to skip processing settings accessed via the GitHub Web UI. ([#12](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/12))

### Changed

- Changed settings for branch protection rules from camel case to snake case notation. ([#37](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/37))
- Removed prefix `organization_` from settings `organization_projects_enabled` and `members_can_change_project_visibility` for organizations. ([#38](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/38))
- Switch to go-jsonnet and use released version `v0.20.0` in the container image. ([#25](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/25))
- Use released version `v0.5.1` of `jsonnet-bundler` in the container image. ([#24](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/24))
- Update some repo settings after creation as they are not taken correctly into account during creation by GitHub.
- Added special handling for `web_commit_signoff_required`: if changed organization wide, it will implicitly change the same setting on repo level.
- Removed `restricts_pushes` setting from branch protection rules as it is implicitly set based on setting `push_restrictions`.
