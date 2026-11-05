Definition of an organization `Team`, the following properties are supported:

| Key                             | Value                            | Description                                                                          | Note                                  |
|---------------------------------|----------------------------------|--------------------------------------------------------------------------------------|---------------------------------------|
| _name_                          | string                           | The name of the team                                                                 |                                       |
| _description_                   | string                           | The description of the team                                                          |                                       |
| _privacy_                       | string                           | The level of privacy this team should have                                           | `visible` or `secret`                 |
| _notifications_                 | boolean                          | Whether the team members receive notifications when the team is @mentioned           |                                       |
| _members_                       | list[string]                     | List of users that should be a member of the team                                    |                                       |
| _skip_members_                  | boolean                          | If `true`, team members will be ignored                                              |                                       |
| _skip_non_organization_members_ | boolean                          | If `true`, users which are not yet organization members can not be added to the team |                                       |
| _team_sync_                     | list\[[TeamSync](team-sync.md)\] | List of identity provider groups connected to the team via team synchronization      | GitHub Enterprise Cloud only          |
| _external_group_id_             | integer or null                  | The id of the external group connected to the team                                   | Enterprise Managed Users (EMU) only   |

## Identity provider integration

The membership of a team can be managed by an identity provider (IdP), with one of these mechanisms:

- **team synchronization** (`team_sync`): one or more IdP groups are connected to the team, available for
  organizations on GitHub Enterprise Cloud with team synchronization enabled
- **external groups** (`external_group_id`): a single external group is connected to the team, available for
  organizations that are part of an enterprise using Enterprise Managed Users

Both mechanisms are mutually exclusive. The members of a team connected to an IdP are provisioned by the IdP,
so `members` must not be set for such a team, and the current members of the team are ignored.

The connections to IdP groups are only retrieved from GitHub if the default configuration supports them,
i.e. defines the `newTeamSync` function for team synchronization, or the `external_group_id` property in
`newTeam` for external groups. If a mechanism is not available for an organization, it is skipped.

## Jsonnet Function

``` jsonnet
orgs.newTeam('<name>') {
  <key>: <value>
}
```

## Validation rules

- setting `privacy` must be one of `visible` or `secret`, any other value triggers an error
- specifying a non-empty list of `members` while `skip_members` is enabled, triggers an error
- specifying a user in `members` that is not yet an organization member while `skip_non_organization_members` is enabled, triggers an error
- specifying both `team_sync` and `external_group_id`, triggers an error
- specifying a non-empty list of `members` for a team connected to an identity provider group, triggers an error
- specifying the same group `id` more than once in `team_sync`, triggers an error

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('OtterdogTest') {
      ...
      teams+: [
        orgs.newTeam('committers') {
          description: "The project committers",
          privacy: "visible",
        },
        orgs.newTeam('admins') {
          description: "The project admins, managed by the identity provider",
          privacy: "secret",
          external_group_id: 1234,
        },
      ],
      ...
    }
    ```
