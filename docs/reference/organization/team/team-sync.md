Definition of an identity provider (IdP) group connected to a `Team` via
[team synchronization](https://docs.github.com/en/enterprise-cloud@latest/organizations/organizing-members-into-teams/synchronizing-a-team-with-an-identity-provider-group),
the following properties are supported:

| Key           | Value  | Description                         | Note                       |
|---------------|--------|-------------------------------------|----------------------------|
| _id_          | string | The id of the IdP group             | identifies the group       |
| _name_        | string | The name of the IdP group           | required by the GitHub API |
| _description_ | string | The description of the IdP group    |                            |

The available IdP groups of an organization, including their id, name and description, can be listed with the
[GitHub REST API](https://docs.github.com/en/enterprise-cloud@latest/rest/teams/team-sync#list-idp-groups-for-an-organization).

Team synchronization requires an organization on GitHub Enterprise Cloud with team synchronization enabled,
it is not available for organizations that are part of an enterprise using Enterprise Managed Users.

Like other resources managed by otterdog, a group that is removed from `team_sync` is only disconnected
from the team when applying the configuration with deletions enabled (`--delete-resources`).

## Jsonnet Function

``` jsonnet
orgs.newTeamSync('<id>') {
  <key>: <value>
}
```

## Validation rules

- an empty `id` or `name` triggers an error

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('OtterdogTest') {
      ...
      teams+: [
        orgs.newTeam('admins') {
          description: "The project admins",
          privacy: "secret",
          team_sync: [
            orgs.newTeamSync('5d4b0a8e-2c19-4b5f-8d6c-1f2e3a4b5c6d') {
              name: "git-admins",
              description: "Admin access via IdP",
            },
          ],
        },
      ],
      ...
    }
    ```
