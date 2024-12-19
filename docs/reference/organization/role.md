Definition of a custom `Role` on organization level, the following properties are supported:

| Key           | Value          | Description                                               | Note                                           |
|---------------|----------------|-----------------------------------------------------------|------------------------------------------------|
| _name_        | string         | The name of the role                                      |                                                |
| _description_ | string         | The description of the role                               |                                                |
| _permissions_ | list[string]   | List of additional permissions                            | TODO                                           |
| _base_role_   | string         | The system role from which this role inherits permissions | `none`, `read`, `write`, `maintain` or `admin` |

## Jsonnet Function

``` jsonnet
orgs.newOrgRole('<name>') {
  <key>: <value>
}
```

## Validation rules

- specifying a non-empty list of `permissions` while `base_role` is set to `none` triggers an error

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('OtterdogTest') {
      ...
      roles+: [
        orgs.newOrgRole('security_team') {
          description: "The security team role",
          permissions+: [
            "delete_alerts_code_scanning",
            "org_review_and_manage_secret_scanning_bypass_requests",
            "read_code_scanning",
            "resolve_dependabot_alerts",
            "resolve_secret_scanning_alerts",
            "view_dependabot_alerts",
            "view_secret_scanning_alerts",
            "write_code_scanning",
          ],
          base_role: "read",
        },
      ],
      ...
    }
    ```
