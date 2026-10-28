# Organization-wide policies

*This page is intended for administrators who maintain the default configuration and the otterdog setup for several
organizations. For the configuration of a single organization, see the [Configuration Guides](../userguide/guides/index.md).*

Otterdog offers several mechanisms to establish common rules across organizations. They differ in whether an
organization can deviate from them:

| Mechanism                                                    | Effect                                                         | Deviation by an organization                         |
|--------------------------------------------------------------|----------------------------------------------------------------|------------------------------------------------------|
| [Default configuration](#the-default-configuration-as-baseline) | provides the inherited value of every property               | override the property in the configuration          |
| [Validation scripts](#enforce-settings-with-validation-scripts) | reject configurations that do not comply                     | not possible, unless the script allows it            |
| [Blueprints](../reference/blueprints/index.md)               | open pull requests that add missing configuration or files     | close the pull request, which dismisses the blueprint |
| [Policies](../reference/policies/index.md)                   | enforce a behavior, e.g. cancel workflow jobs on certain runners | only with a policy of the same type on organization level |

## The default configuration as baseline

The default configuration, referenced by `base_template` in `otterdog.json`, provides the inherited value of every
property and defines which settings and resources otterdog manages, see
[Inherited and explicit values](../userguide/guides/inheritance.md).

- Keep the default configuration in its own repository, protect it like code and publish released versions, e.g.
  as tags, which `base_template` references.
- Before releasing a new version, run `plan` for the affected organizations: every changed default applies to all
  resources that do not override it.
- Adding a setting or a resource type to the default configuration makes otterdog manage it for every
  organization, e.g. defining `team_permissions` for repositories makes the team permissions of all repositories
  authoritative.

## Enforce settings with validation scripts

The directory of the default configuration, i.e. the root of the repository referenced by `base_template`, can
contain Python scripts that otterdog executes during validation:

| Script                     | Executed for                    | Available variables                                                         |
|----------------------------|---------------------------------|-----------------------------------------------------------------------------|
| `validate-org-settings.py` | the organization settings       | `self`: the organization settings, `context`: the validation context        |
| `validate-team.py`         | every team                      | `self`: the team, `context`: the validation context                         |

`context.property_equals(self, '<key>', <value>)` reports an error if a property does not have the required value,
`context.add_failure(...)` reports any other failure. For example, the following `validate-org-settings.py` requires
that members get no access to repositories by default and that two-factor authentication is required:

``` python
context.property_equals(self, "default_repository_permission", "none")
context.property_equals(self, "two_factor_requirement", True)
```

Similarly, scripts can run when `apply` creates resources:

| Script                     | Executed                                   | Available variables                                                 |
|----------------------------|--------------------------------------------|---------------------------------------------------------------------|
| `pre-add-object-hook.py`   | before each resource is created            | `model_object`: the resource, `org_config`, `self`: the operation   |
| `post-add-objects-hook.py` | after all resources have been created      | `patches`: the applied additions, `org_config`, `self`: the operation |

!!! warning

    These scripts are executed as Python code by otterdog, with the permissions and credentials of the process that
    runs it. Anybody who can change the default configuration can therefore run code in this context. Restrict and
    review changes to the repository of the default configuration accordingly, and reference released versions
    only.

## Teams managed by another tool

When teams are created and maintained by another tool, e.g. a synchronization with an identity provider, exclude
them from otterdog with regular expressions that are matched against the team slugs:

``` json
{
  "defaults": {
    "github": {
      "exclude_teams": [
        ".*-committers",
        "^sync-.*"
      ]
    }
  }
}
```

Excluded teams are not imported, and defining them in the configuration of an organization is reported as error,
unless they are defined by the default configuration. Their permissions on repositories are ignored as well, unless
a repository lists the team in `team_permissions`, see
[Teams and access](../userguide/guides/teams-and-access.md#grant-teams-access-to-repositories).

The repository that holds the configuration of each organization is set with `config_repo` in the same `github`
section, `.otterdog` by default. It is used by the `fetch-config` and `push-config` operations.

## Exceptions

Common rules need exceptions from time to time. Make them visible and reviewable:

- document the reason of an override in the configuration of the organization with a comment
- require a review by the team that owns the rule for such changes, e.g. with a `CODEOWNERS` file in the
  configuration repository
- if a validation script enforces the rule, keep the list of exceptions in the script, so that it is reviewed
  centrally

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    // Exception to the organization-wide default: the project publishes its documentation
    // from private repositories, which requires read access for all members.
    default_repository_permission: "read",
  },
}
```

## Cost-related changes

Changes that may incur costs, e.g. a larger GitHub Actions cache, can require a review by a designated team, see
[Cost policy](setup.md#cost-policy).

## Environments managed by another tool

Repository environments that are created and maintained by another tool can be excluded from otterdog with regular
expressions that are matched against the environment names:

``` json
{
  "defaults": {
    "github": {
      "exclude_environments": [
        "^external-.*"
      ]
    }
  }
}
```

Excluded environments, including their secrets and variables, are ignored when reading the live state of a
repository, unless the repository declares an environment with that name in its configuration.
