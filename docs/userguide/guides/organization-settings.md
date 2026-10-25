# Organization settings and member privileges

The [organization settings](../../reference/organization/settings.md) define what members can do in the
organization and the policies that apply to all repositories. This guide covers the settings related to the
security and the governance of the organization. The base permission of members is covered in
[Teams and access](teams-and-access.md), the security managers in
[Repository security features](repository-security.md#organization-settings-related-to-security).

## Require two-factor authentication

Requiring two-factor authentication protects the organization against compromised passwords: members and outside
collaborators without two-factor authentication are removed from the organization when it is enabled, see
[Requiring two-factor authentication in your organization](https://docs.github.com/en/organizations/keeping-your-organization-secure/managing-two-factor-authentication-for-your-organization/requiring-two-factor-authentication-in-your-organization).

`two_factor_requirement` is a read-only setting in otterdog: GitHub does not allow changing it through its API, it
is enabled in the GitHub web interface by an owner of the organization. The configuration shows its current value
after an `import`.

!!! tip "Recommendation"

    Require two-factor authentication in every organization, and check the members who did not enable it before
    enabling the requirement, as they lose their access.

## Restrict what members can do

The following settings define which actions are reserved to the owners of the organization:

| Setting                                   | When enabled, members ...                                                          |
|-------------------------------------------|------------------------------------------------------------------------------------|
| `members_can_create_public_repositories`  | can create public repositories                                                     |
| `members_can_create_private_repositories` | can create private repositories                                                    |
| `members_can_fork_private_repositories`   | can fork the private repositories of the organization                              |
| `members_can_change_repo_visibility`      | with admin permission on a repository can change its visibility                    |
| `members_can_delete_repositories`         | with admin permission on a repository can delete or transfer it                    |
| `members_can_delete_issues`               | with admin permission on a repository can delete its issues                        |
| `members_can_create_teams`                | can create teams                                                                   |

The example default configuration disables all of them, so that repositories are only created, deleted or made
public through the configuration. An organization that lets its members create teams and delete spam issues
enables these settings:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    members_can_create_teams: true,
    members_can_delete_issues: true,
  },
}
```

!!! info "Organization policy"

    When repositories are managed with otterdog, the configuration declares all the repositories of the
    organization:

    - a repository created in the GitHub web interface is not declared: `plan` reports it as a deletion, and
      applying the configuration with deletions enabled (`--delete-resources`) deletes it;
    - a repository deleted in the GitHub web interface is still declared: `plan` reports it as an addition, and
      applying the configuration creates it again, without its content, whether deletions are enabled or not.

    Keeping repository creation and deletion reserved to owners makes the configuration the single place where
    repositories are added and removed, see [Adding a repository](../adding.md).

!!! note

    Some settings, e.g. `members_can_create_teams`, `members_can_delete_issues`, `members_can_delete_repositories`
    and `members_can_change_repo_visibility`, can only be read and changed through the GitHub web interface.
    Otterdog applies them with the credentials of a user that can log in to GitHub, see
    [Setup](../../operating_otterdog/setup.md). Changes to these settings that are merged in a pull request of the
    configuration repository have to be applied manually.

## Require a sign-off for commits made in the web interface

Some projects require contributors to sign off their commits, e.g. to confirm a developer certificate of origin.
`web_commit_signoff_required` makes GitHub add the sign-off to the commits that are made in its web interface, e.g.
when editing a file or applying a suggestion, see
[Managing the commit signoff policy for your organization](https://docs.github.com/en/organizations/managing-organization-settings/managing-the-commit-signoff-policy-for-your-organization).

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    web_commit_signoff_required: true, // (1)!
  },
  _repositories+:: [
    orgs.newRepo('my-repo'),
  ],
}
```

1. When enabled on the organization, it applies to all repositories: a repository that disables it is reported as
   warning by `validate`, and its setting is ignored.

The sign-off of commits pushed from a local clone is added by the contributor, e.g. with `git commit -s`. It is
not checked by this setting, but by a status check of a service or a workflow, which can be required with a
ruleset, see [Require status checks](branch-protection.md#require-status-checks).

## Classify repositories with custom properties

[Custom properties](../../reference/organization/custom-property.md) add structured metadata to repositories,
e.g. their category or their maturity. The organization defines the properties and their allowed values, each
repository sets its values:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    custom_properties+: [
      orgs.newCustomProperty('category') {
        description: "Category used to group repositories",
        value_type: "single_select",
        allowed_values: [
          "library",
          "tool",
          "website",
          "other",
        ],
        required: true,
        default_value: "other", // (1)!
      },
    ],
  },
  _repositories+:: [
    orgs.newRepo('my-library') {
      custom_properties: {
        category: "library",
      },
    },
  ],
}
```

1. A required property needs a default value, which GitHub assigns to the repositories that do not set the
   property.

Custom properties can be used to filter the repositories of the organization on GitHub, and by tools that read
them through the GitHub API, e.g. to generate an overview of the repositories, see
[Managing custom properties for repositories in your organization](https://docs.github.com/en/organizations/managing-organization-settings/managing-custom-properties-for-repositories-in-your-organization).

!!! warning

    The `value_type` of a custom property cannot be changed once the property exists: GitHub rejects the change,
    which is only detected when the configuration is applied. Remove the property and create a new one instead.

Organization rulesets can target repositories by custom properties on GitHub, but otterdog only supports targeting
them by name, see [Organization-wide rulesets](organization-rulesets.md#target-repositories-by-name).
