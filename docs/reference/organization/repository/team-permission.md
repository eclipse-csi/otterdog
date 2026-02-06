Definition of a `Team Permission`, the following properties are supported:

| Key                        | Value                                   | Description                                                                           | Notes                                                                                                                                                                   |
|----------------------------|-----------------------------------------|---------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| _name_                     | string                                  | The name of the team in the organization.                                             |                                                                                                                                                                         |
| _permission_               | string                                  | The name of the permission.                                                           | allowed are the following: `pull`, `triage`, `push`, `maintain`, `admin` or `READ`, `WRITE`, `MAINTAIN`, `TRIAGE`, `ADMIN` (The latter values come from github graphql) |

## Jsonnet Function

``` jsonnet
orgs.newTeamPermission('<name>') {
  <key>: <value>
}
```

## Validation rules

- allowed values are the following `pull`, `triage`, `push`, `maintain`, `admin` or `READ`, `WRITE`, `MAINTAIN`, `TRIAGE`, `ADMIN`.

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('OtterdogTest') {
      ...
      _repositories+:: [
        ...
        orgs.newRepo('test-repo') {
          ...
          team_permissions: [
            orgs.newTeamPermission('team') {
              permission: "maintain",
            },
          ],
        }
      ]
    }
    ```
