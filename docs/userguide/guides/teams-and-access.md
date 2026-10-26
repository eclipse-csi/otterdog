# Teams and access

Access to the repositories of an organization results from the base permission of the organization, the teams and
their permissions on repositories, and individual collaborators. Otterdog manages the first two; individual
collaborators cannot be managed with otterdog.

## Base permission

The organization setting `default_repository_permission` grants a permission on all repositories to every member
of the organization: `none`, `read`, `write` or `admin`, see
[Setting base permissions for an organization](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/setting-base-permissions-for-an-organization).
Members keep higher permissions that they get from a team.

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    default_repository_permission: "none",
  },
}
```

!!! info "Organization policy"

    With `none`, every access must be granted explicitly through a team, which makes access reviewable in the
    configuration. With `read`, all members can read private repositories, which eases collaboration in
    organizations whose members all work on the same projects. A base permission of `write` or `admin` is rarely
    appropriate, as it grants access to every new repository.

Related settings restrict what members can do on organization level, e.g. `members_can_create_public_repositories`,
`members_can_create_teams` or `members_can_delete_repositories`, see
[Organization Settings](../../reference/organization/settings.md).

## Teams

Teams are defined with [`orgs.newTeam`](../../reference/organization/team.md). Their members can be managed in the
configuration or elsewhere:

| Members managed ...                                     | Configuration                                                                                 |
|---------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| in the configuration                                    | `members` lists the GitHub logins                                                             |
| elsewhere, e.g. in the GitHub web interface             | `skip_members: true`, otterdog manages the team but ignores its members                       |
| by an external tool, including the team itself          | the team is excluded with `exclude_teams`, see [Organization-wide policies](../../operating_otterdog/organization-policies.md#teams-managed-by-another-tool) |

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  teams+: [
    orgs.newTeam('maintainers') {
      description: "Maintainers of the project",
      members+: [
        "alice",
        "bob",
      ],
    },
    orgs.newTeam('contributors') {
      description: "Contributors, managed in the GitHub web interface",
      skip_members: true,
    },
  ],
}
```

!!! note

    Adding a user who is not yet a member of the organization to a team invites this user to the organization.
    With `skip_non_organization_members: true`, `validate` instead reports such users as an error, so that
    invitations stay under the control of another process.

Teams with `privacy: "secret"` are only visible to their members and organization owners. Secret teams cannot be
used as bypass actors of rulesets, see
[Creating rulesets for a repository](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository#granting-bypass-permissions-for-your-branch-or-tag-ruleset).

## Grant teams access to repositories

The repository property `team_permissions` maps the slug of a team to its permission on the repository:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  teams+: [
    orgs.newTeam('maintainers'),
    orgs.newTeam('documentation'),
  ],
  _repositories+:: [
    orgs.newRepo('my-repo') {
      team_permissions+: {
        maintainers: "maintain",
        documentation: "triage",
      },
    },
  ],
}
```

The permissions and their GitHub roles are listed in [Team Permissions](../../reference/organization/repository/index.md#team-permissions),
see also [Repository roles for an organization](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization).

!!! warning

    When the default configuration defines `team_permissions`, as the example default configuration does, the
    team permissions of every repository are managed: a team that has access to a repository on GitHub but is not
    listed in its configuration loses its access the next time the configuration is applied. As the removal is a
    modification of the repository, it is applied even without `--delete-resources`. This also applies to teams
    whose members are managed outside otterdog. Review such removals with `plan` before applying.

    The permissions of teams excluded with `exclude_teams` are ignored, unless the repository lists the team in
    `team_permissions`, see
    [Organization-wide policies](../../operating_otterdog/organization-policies.md#teams-managed-by-another-tool).

!!! tip "Recommendation"

    Grant the lowest permission that fits the role of a team, e.g. `maintain` instead of `admin` for maintainers,
    and grant access through teams rather than to individual users, so that access can be reviewed in one place.

## Security managers and custom roles

- The organization setting `security_managers` assigns the security manager role to teams, see
  [Repository security features](repository-security.md#organization-settings-related-to-security).
- Custom organization roles can be defined with [`orgs.newOrgRole`](../../reference/organization/role.md). They
  require the `enterprise` plan.
