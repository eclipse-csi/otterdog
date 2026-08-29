Definition of a `TeamSync` for a team, the following properties are supported:

| Key            | Value    | Description                                          | Note                 |
|----------------|----------|------------------------------------------------------|----------------------|
| _id_           | string   |The unique identifier of the IdP group                |                      |
| _name_         | string   |The name of the IdP group (informational, obligatory) |                      |
| _description_  | string   |Human‑readable description of the IdP group           |                      |


## Jsonnet Function

``` jsonnet
orgs.newTeamSync('<name>') {
  <key>: <value>
}
```

## Validation rules

- each `TeamSync` entry **must define `id`, `name` and `description`**
- `id`, `name` and `description` **must be non-empty strings**
- omitting any of these fields prevents successful synchronization with GitHub Enterprise Cloud


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
            orgs.newTeamSync('git-admin') {
              id: "1234567890",
              description: "Admin access via IdP",
            },
          ],
        },
      ],
    ...
    }
    ```
