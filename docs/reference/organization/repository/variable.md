Definition of a `Variable` on repository level, the following properties are supported:

| Key                     | Value          | Description              | Note |
|-------------------------|----------------|--------------------------|------|
| _name_                  | string         | The name of the variable |      |
| _value_                 | string         | The variable value       |      |

## Jsonnet Function

``` jsonnet
orgs.newRepoVariable('<name>') {
  <key>: <value>
}
```

## Validation rules

- None

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('OtterdogTest') {
      ...
      _repositories+:: [
        ...
        orgs.newRepo('test-repo') {
          ...
          variables+: [
            orgs.newRepoVariable('TEST_VARIABLE') {
              value: "TESTVALUE",
            },
          ],
        }
      ]
    }
    ```
