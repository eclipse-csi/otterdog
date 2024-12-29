Definition of an organization `Team`, the following properties are supported:

| Key             | Value        | Description                                                                | Note                  |
|-----------------|--------------|----------------------------------------------------------------------------|-----------------------|
| _name_          | string       | The name of the team                                                       |                       |
| _description_   | string       | The description of the team                                                |                       |
| _privacy_       | string       | The level of privacy this team should have                                 | `visible` or `secret` |
| _notifications_ | boolean      | Whether the team members receive notifications when the team is @mentioned |                       |
| _members_       | list[string] | List of users that should be a member of the team                          |                       |
| _skip_members_  | boolean      | If `true`, team membership will not be modified                            |                       |


## Jsonnet Function

``` jsonnet
orgs.newTeam('<name>') {
  <key>: <value>
}
```

## Validation rules

- setting `privacy` must be one of `visible or `secret`, any other value triggers an error

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
