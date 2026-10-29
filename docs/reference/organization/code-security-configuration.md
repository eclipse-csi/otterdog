Definition of a `Code Security Configuration` on organization level, the following properties are supported:

| Key                                                  | Value                  | Description                                                                                          | Notes                                                                                                             |
|------------------------------------------------------|------------------------|------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|
| _name_                                               | string                 | The name of the code security configuration                                                          | Must be unique within the organization                                                                            |
| _description_                                        | string                 | The description of the code security configuration                                                   | At most 255 characters                                                                                            |
| _code_security_                                      | string                 | The enablement status of GitHub Code Security                                                        | `enabled` or `disabled`                                                                                           |
| _secret_protection_                                  | string                 | The enablement status of GitHub Secret Protection                                                    | `enabled` or `disabled`                                                                                           |
| _dependency_graph_                                   | string                 | The enablement status of the dependency graph                                                        | `enabled`, `disabled` or `not_set`                                                                                |
| _dependency_graph_autosubmit_action_                 | string                 | The enablement status of automatic dependency submission                                             | `enabled`, `disabled` or `not_set`                                                                                |
| _dependency_graph_autosubmit_action_labeled_runners_ | boolean or null        | If automatic dependency submission uses runners labeled with `dependency-submission`                 | `null` if not managed                                                                                             |
| _dependabot_alerts_                                  | string                 | The enablement status of Dependabot alerts                                                           | `enabled`, `disabled` or `not_set`                                                                                |
| _dependabot_security_updates_                        | string                 | The enablement status of Dependabot security updates                                                 | `enabled`, `disabled` or `not_set`                                                                                |
| _dependabot_reachability_                            | string or null         | The enablement status of reachability analysis for Dependabot                                        | `enabled`, `disabled`, `not_set` or `null` if not managed                                                         |
| _dependabot_delegated_alert_dismissal_               | string or null         | The enablement status of Dependabot delegated alert dismissal                                        | `enabled`, `disabled`, `not_set` or `null` if not managed                                                         |
| _code_scanning_default_setup_                        | string                 | The enablement status of code scanning default setup                                                 | `enabled`, `disabled` or `not_set`                                                                                |
| _code_scanning_default_setup_runner_type_            | string or null         | The type of runners code scanning default setup uses                                                 | `standard`, `labeled`, `not_set` or `null` if not managed                                                         |
| _code_scanning_default_setup_runner_label_           | string or null         | The label of the runners code scanning default setup uses                                            | Only taken into account if `code_scanning_default_setup_runner_type` is `labeled`                                 |
| _code_scanning_allow_advanced_                       | boolean or null        | If repositories using code scanning advanced setup are allowed                                       | `null` if not managed                                                                                             |
| _code_scanning_delegated_alert_dismissal_            | string or null         | The enablement status of code scanning delegated alert dismissal                                     | `enabled`, `disabled`, `not_set` or `null` if not managed                                                         |
| _secret_scanning_                                    | string                 | The enablement status of secret scanning                                                             | `enabled`, `disabled` or `not_set`                                                                                |
| _secret_scanning_push_protection_                    | string                 | The enablement status of secret scanning push protection                                             | `enabled`, `disabled` or `not_set`                                                                                |
| _secret_scanning_delegated_bypass_                   | string                 | The enablement status of delegated bypass for push protection                                        | `enabled`, `disabled` or `not_set`                                                                                |
| _secret_scanning_delegated_bypass_reviewers_         | list[string] or null   | List of teams or roles that review requests to bypass push protection                                | see [Bypass Reviewers](#bypass-reviewers), `null` if not managed                                                  |
| _secret_scanning_validity_checks_                    | string                 | The enablement status of secret scanning validity checks                                             | `enabled`, `disabled` or `not_set`                                                                                |
| _secret_scanning_non_provider_patterns_              | string                 | The enablement status of secret scanning of non-provider patterns                                    | `enabled`, `disabled` or `not_set`                                                                                |
| _secret_scanning_generic_secrets_                    | string or null         | The enablement status of Copilot secret scanning                                                     | `enabled`, `disabled`, `not_set` or `null` if not managed                                                         |
| _secret_scanning_generic_secrets_push_protection_    | string or null         | The enablement status of push protection for generic secrets                                         | `enabled`, `disabled`, `not_set` or `null` if not managed                                                         |
| _secret_scanning_delegated_alert_dismissal_          | string or null         | The enablement status of secret scanning delegated alert dismissal                                   | `enabled`, `disabled`, `not_set` or `null` if not managed                                                         |
| _secret_scanning_extended_metadata_                  | string or null         | The enablement status of secret scanning extended metadata                                           | `enabled`, `disabled`, `not_set` or `null` if not managed                                                         |
| _private_vulnerability_reporting_                    | string                 | The enablement status of private vulnerability reporting                                             | `enabled`, `disabled` or `not_set`                                                                                |
| _enforcement_                                        | string                 | If repositories the configuration is attached to can change its settings                             | `enforced` or `unenforced`                                                                                        |
| _default_for_new_repos_                              | string                 | The visibility of new repositories the configuration is attached to by default                       | `none`, `all`, `public` or `private_and_internal`                                                                 |

A feature set to `not_set` is not changed on the repositories the configuration is attached to, while properties set
to `null` are not managed by otterdog, e.g. because the feature is not available to every organization.

Only configurations of the organization are managed, the predefined configurations of GitHub (e.g. `GitHub recommended`)
and configurations of an enterprise are neither created, updated nor deleted. The name identifies a configuration: renaming a configuration deletes
it and creates a new one, which is not attached to the repositories of the previous configuration anymore.

A configuration is attached to a repository with the `code_security_configuration` property of the
[Repository](repository/index.md), and to new repositories with the `default_for_new_repos` property. The
configuration is attached before the other settings of the repository are applied, and otterdog waits until GitHub
completed the attachment, as well as until an updated configuration is applied to its repositories. The patches of
the repositories that an update is not applied to, as it failed or is still pending after 30 seconds, are skipped and
reported as errors, as they might depend on the updated settings, as well as the patches of the repositories attached to
a configuration whose update or deletion failed, or of all repositories if the attached ones can not be retrieved. Archived repositories support code security
configurations, only secret scanning runs while they are archived.

The settings of a repository that the configuration attached to it sets are not managed on the repository, as the
configuration takes precedence, and changing them on the repository might detach it from its configuration. This
applies to the configuration the repository specifies, otherwise the one currently attached to it, even if it is not
managed (e.g. `GitHub recommended`) or not deleted as `--delete-resources` is not used, or for a new repository, the
default configuration for its visibility, unless `default_code_security_configurations_disabled` is enabled:

| Feature of the configuration      | Settings of the repository                                                                                 |
|-----------------------------------|------------------------------------------------------------------------------------------------------------|
| `dependabot_alerts`               | `dependabot_alerts_enabled`                                                                                |
| `dependabot_security_updates`     | `dependabot_security_updates_enabled`                                                                      |
| `code_scanning_default_setup`     | `code_scanning_default_setup_enabled`, `code_scanning_default_query_suite`, `code_scanning_default_languages` |
| `secret_scanning`                 | `secret_scanning`                                                                                          |
| `secret_scanning_push_protection` | `secret_scanning_push_protection`                                                                          |
| `private_vulnerability_reporting` | `private_vulnerability_reporting_enabled`                                                                  |

Features set to `not_set` leave the settings of the repository unchanged, they are still managed on the repository.
GitHub supports private vulnerability reporting only on public repositories, a configuration does not enable it on
private repositories. For a feature that the configuration does not specify, its current value on GitHub applies. When the current settings
of repositories are not retrieved from GitHub, e.g. for the local apply of the dashboard, the settings that their
configuration stops setting are applied again, as the configuration might have changed them on GitHub.

!!! note

    To use a code security configuration as default for new repositories, the setting
    `default_code_security_configurations_disabled` of the [Organization Settings](settings.md) must be disabled,
    as it removes any default code security configuration otherwise.

## Bypass Reviewers

The entries of `secret_scanning_delegated_bypass_reviewers` reference teams and roles like the
[bypass actors](repository/bypass-actor.md) of rulesets:

| Reviewer             | Format                    | Example                                                        |
|----------------------|---------------------------|----------------------------------------------------------------|
| Team                 | `@<organization>/<team>`  | `@OtterdogTest/security-team`                                  |
| Role                 | `#<role>`                 | `#OrganizationAdmin`, `#RepositoryAdmin`, `#Maintain`, `#Write` |
| Custom role          | `#<role-id>`              | `#4711`                                                        |

By default, a reviewer reviews the requests to bypass push protection. With the suffix `:exempt`, e.g.
`@OtterdogTest/release-bots:exempt`, the reviewer is exempt from push protection instead.

## Jsonnet Function

``` jsonnet
orgs.newOrgCodeSecurityConfiguration('<name>') {
  <key>: <value>
}
```

## Default values

The default configuration of otterdog creates a code security configuration with the following values. Its features
are disabled, except the dependency graph: attaching a configuration disables the features it does not enable on the
repository, set a feature to `not_set` to leave it to the repositories.

``` jsonnet
--8<-- "otterdog/resources/defaults/otterdog-defaults.libsonnet:code_security_configuration"
```

The default configuration of an instance of otterdog, set by `base_template`, might define other values, see
`otterdog show-default` or the Defaults page of a project in the dashboard.

## Validation rules

- specifying a value that is not allowed for a property triggers an error
- specifying a `description` longer than 255 characters triggers an error
- setting `code_scanning_default_setup_runner_type` to `labeled` without a `code_scanning_default_setup_runner_label` triggers an error
- specifying a bypass reviewer that is neither a team nor a role, or with a mode other than `always` or `exempt`, triggers an error
- setting the same visibility of new repositories in `default_for_new_repos` of several configurations triggers an error
- setting `default_for_new_repos` while `default_code_security_configurations_disabled` of the organization settings is enabled triggers an error
- enabling a feature of secret scanning while `secret_protection` is disabled triggers an error
- enabling `code_scanning_default_setup` or `code_scanning_delegated_alert_dismissal` while `code_security` is disabled triggers an error
- setting `code_security` and `secret_protection` to a different status for an organization with free plan triggers an error
- enabling `secret_scanning_delegated_bypass` without any `secret_scanning_delegated_bypass_reviewers` triggers a warning
- enabling a feature of secret scanning while `secret_scanning` is disabled triggers a warning
- enabling `secret_scanning_delegated_bypass` while `secret_scanning_push_protection` is disabled triggers a warning
- enabling `dependabot_security_updates` while `dependabot_alerts` is disabled triggers a warning

!!! note

    Enabling `code_security` or `secret_protection` can consume GitHub Advanced Security licenses for the private
    and internal repositories the configuration is attached to. Such changes are considered to be cost-related if
    private repositories are attached to the configuration or it is the default for new private repositories, and
    so is attaching a private repository to a configuration that enables them. This does not apply to an
    organization with free plan, for which these products cannot be purchased.
    Setting `code_security` and `secret_protection` to a different status requires an unbundled GitHub Advanced
    Security plan, i.e. GitHub Code Security and GitHub Secret Protection, which is not available for an organization
    with free plan. GitHub rejects it otherwise.

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      settings+: {
        default_code_security_configurations_disabled: false,
      },
      code_security_configurations+: [
        orgs.newOrgCodeSecurityConfiguration('baseline') {
          description: "Baseline configuration for all new repositories",
          code_security: "enabled",
          secret_protection: "enabled",
          dependabot_alerts: "enabled",
          dependabot_security_updates: "enabled",
          secret_scanning: "enabled",
          secret_scanning_push_protection: "enabled",
          secret_scanning_delegated_bypass: "enabled",
          secret_scanning_delegated_bypass_reviewers: [
            "#OrganizationAdmin",
          ],
          default_for_new_repos: "all",
        },
      ],
      _repositories+:: [
        orgs.newRepo('my-repo') {
          code_security_configuration: "baseline",
        },
      ],
    }
    ```
