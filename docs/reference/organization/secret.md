Definition of a `Secret` on organization level, the following properties are supported:

| Key                     | Value                          | Description                                    | Note                                                 |
|-------------------------|--------------------------------|------------------------------------------------|------------------------------------------------------|
| _name_                  | string                         | The name of the secret                         |                                                      |
| _selected_repositories_ | list[string]                   | List of repositories that can use the secret   | only applicable if `visibility` is set to `selected` |
| _value_                 | [SecretValue](secret-value.md) | The secret value                               |                                                      |
| _visibility_            | string                         | Controls which repositories can use the secret | `public`, `private` or `selected`                    |

The value should reference a credential provider instead of being written in clear text, see
[SecretValue](secret-value.md).

## Jsonnet Function

``` jsonnet
orgs.newOrgSecret('<name>') {
  <key>: <value>
}
```

## Validation rules

- redacted secret values (`********`) trigger a validation info and will skip the secret during processing
- `visibility` of `private` is not supported by GitHub with a billing plan of type `free`
- specifying a non-empty list of `selected_repositories` while `visibility` is not set to `selected` triggers a warning

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('OtterdogTest') {
      ...
      secrets+: [
        orgs.newOrgSecret('TEST_SECRET') {
          selected_repositories+: [
            "test-repo"
          ],
          value: "pass:path/to/my/secret/value",
          visibility: "selected",
        },
      ],
      ...
    }
    ```
