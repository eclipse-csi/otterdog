Definition of a `Variable` on repository environment level, the following properties are supported:

| Key                     | Value          | Description              | Note |
|-------------------------|----------------|--------------------------|------|
| _name_                  | string         | The name of the variable |      |
| _value_                 | string         | The variable value       |      |

## Jsonnet Function

``` jsonnet
orgs.newEnvVariable('<name>') {
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
          environments: [
            orgs.newEnvironment('Environment') {
              variables: [
                orgs.newEnvVariable('TEST_VARIABLE') {
                  value: "TESTVALUE",
                },
              ],
            },
          ],
        }
      ]
    }
    ```
