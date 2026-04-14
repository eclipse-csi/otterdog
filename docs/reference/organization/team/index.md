Definition of an organization `Team`, the following properties are supported:

| Key                             | Value        | Description                                                                          | Note                  |
|---------------------------------|--------------|--------------------------------------------------------------------------------------|-----------------------|
| _name_                          | string       | The name of the team                                                                 |                       |
| _description_                   | string       | The description of the team                                                          |                       |
| _privacy_                       | string       | The level of privacy this team should have                                           | `visible` or `secret` |
| _notifications_                 | boolean      | Whether the team members receive notifications when the team is @mentioned           |                       |
| _members_                       | list[string] | List of users that should be a member of the team                                    |                       |
| _skip_members_                  | boolean      | If `true`, team members will be ignored                                              |                       |
| _skip_non_organization_members_ | boolean      | If `true`, users which are not yet organization members can not be added to the team |                       |
| _team_sync_                     | list\[[TeamSync](team-sync.md)\]       | List of IdP groups which are connected to the team via GitHub Enterprise Cloud Team Sync       |                       |
| _external_groups_               | string       | The id of an external group which is provisioned on the enterprise                   | Exclusive with `team_sync`                      |

## Identity provider integration

Teams can be connected to an identity provider either via
GitHub Enterprise Cloud **Team Sync** (`team_sync`) or via
enterprise-wide **external groups** (`external_groups`).

These two mechanisms are **mutually exclusive**.
A team must not define both `team_sync` and `external_groups` at the same time.


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
- `team_sync` and `external_groups` are mutually exclusive and must not be used together

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
      ],
      ...
    }
    ```
