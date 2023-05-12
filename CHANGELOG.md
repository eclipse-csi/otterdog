# Change Log

## [0.1.0.dev] - unreleased

### Added

- Added support for `default_workflow_permissions` setting for organizations. ([#36](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/36))
- Added support for `security_managers` setting for organizations. ([#35](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/35))
- Added support for `is_template` and `template_repository` setting for repository settings. ([#34](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/34))
- Added flag `--update-webhooks` for apply / plan / local-plan operations to force updates of webhooks with secrets. ([#21](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/21))
- Added support for `secret_scanning_push_protection` setting for repository settings. ([#33](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/33))
- Added support for extending list-based properties, e.g. `requiredStatusChecks` for branch protection rules.
- Added operation `local-plan` to output changes that will be applied by based on another local config.
- Added flag `--pull-request` for fetch-config operation to fetch the config from a specific pull request.
- Added support for `requiredStatusChecks` setting for branch protection rules. ([#5](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/5))
- Added flag `--message` for push-config operation to specify the commit message.
- Added support for pre-defined repositories in the default configuration. ([#23](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/23))
- Added option `--no-web-ui` for import operation as well. ([#20](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/20))
- Added request caching for REST api calls. ([#18](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/18))
- Added support for `bypassForcePushAllowances` setting for branch protection rules. ([#5](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/5))
- Added support for `bypassPullRequestAllowances` setting for branch protection rules. ([#5](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/5))
- Added support for `reviewDismissalAllowances` setting for branch protection rules. ([#5](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/5))
- Added support for `pushRestrictions` setting for branch protection rules. ([#5](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/5))
- Added option `--no-web-ui` to skip processing settings accessed via the GitHub Web UI. ([#12](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/12))

### Changed

- Switch to go-jsonnet and use released version `v0.20.0` in the container image. ([#25](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/25))
- Use released version `v0.5.1` of `jsonnet-bundler` in the container image. ([#24](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/24))
- Update some repo settings after creation as they are not taken correctly into account during creation by GitHub.
- Added special handling for `web_commit_signoff_required`: if changed organization wide, it will implicitly change the same setting on repo level.
- Removed `restrictsPushes` setting from branch protection rules as it is implicitly set based on setting `pushRestrictions`.
