# Change Log

## [0.1.0.dev] - unreleased

### Added

- Added support for `bypassForcePushAllowances` setting for branch protection rules. ([#5](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/5))
- Added support for `bypassPullRequestAllowances` setting for branch protection rules. ([#5](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/5))
- Added support for `reviewDismissalAllowances` setting for branch protection rules. ([#5](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/5))
- Added support for `pushRestrictions` setting for branch protection rules. ([#5](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/5))
- Added option `--no-web-ui` to skip processing settings accessed via the GitHub Web UI. ([#12](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/12))

### Changed

- Added special handling for `web_commit_signoff_required`: if changed organization wide, it will implicitly change the same setting on repo level.
- Removed `restrictsPushes` setting from branch protection rules as it is implicitly set based on setting `pushRestrictions`.
