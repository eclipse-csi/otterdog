Definition of a `Variable` on organization level, the following properties are supported:

| Key                     | Value          | Description                                      | Note                                                 |
|-------------------------|----------------|--------------------------------------------------|------------------------------------------------------|
| _name_                  | string         | The name of the variable                         |                                                      |
| _selected_repositories_ | list[string]   | List of repositories that can use the variable   | only applicable if `visibility` is set to `selected` |
| _value_                 | string         | The variable value                               |                                                      |
| _visibility_            | string         | Controls which repositories can use the variable | `public`, `private` or `selected`                    |

## Jsonnet Function

``` jsonnet
orgs.newOrgVariable('<name>') {
  <key>: <value>
}
```

## Validation rules

- `visibility` of `private` is not supported by GitHub with a billing plan of type `free`
- specifying a non-empty list of `selected_repositories` while `visibility` is not set to `selected` triggers a warning

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('OtterdogTest') {
      ...
      variables+: [
        orgs.newOrgVariable('TEST_VARIABLE') {
          selected_repositories+: [
            "test-repo"
          ],
          value: "MYVALUE",
          visibility: "selected",
        },
      ],
      ...
    }
    ```
