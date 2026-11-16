An Allowed Actor represents an entity that is allowed to run the workflows targeted by an
[actions policy](actions-policy.md).
The following format is used to distinguish between the different types of actors that GitHub supports:

| Actor Type   | Format                        | Example                    |
|--------------|-------------------------------|----------------------------|
| Role         | `#<role-name>`                | `#Maintain`                |
| Custom role  | `#<role-id>`                  | `#42`                      |
| User         | `@<github_handle>`            | `@alice`                   |
| Bot          | `@<bot-login>`                | `@dependabot[bot]`         |
| Team         | `@<organization>/<team-slug>` | `@OtterdogTest/committers` |
| App          | `<app-slug>`                  | `eclipse-eca-validation`   |
| Other actors | `<type>:<id>`                 | `EnterpriseTeam:42`        |

The following roles are currently supported by name:

- Write
- Maintain
- RepositoryAdmin
- OrganizationAdmin

An actor whose name otterdog can not resolve is shown with its type and id, e.g. an enterprise team, an app
installation (`IntegrationInstallation:<id>`), an app that is not installed in the organization or a deleted user.
The types are `User`, `Bot`, `Team`, `BusinessTeam`, `EnterpriseTeam`, `IntegrationInstallation`, `App` and
`RepositoryRole`.

!!! note

    The features of GitHub, e.g. Dependabot version updates, are not blocked by actions policies. A workflow that
    is run by the identity of such a feature, e.g. `dependabot[bot]`, is blocked unless this identity is an
    allowed actor.
