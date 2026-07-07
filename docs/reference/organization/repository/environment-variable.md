Definition of a `Variable` on environment level, the following properties are supported:

| Key                     | Value          | Description              | Note |
|-------------------------|----------------|--------------------------|------|
| _name_                  | string         | The name of the variable |      |
| _value_                 | string         | The variable value       |      |

## Jsonnet Function

``` jsonnet
orgs.newEnvironmentVariable('<name>') {
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
            orgs.newEnvironment('linux') {
              ...
              variables+: [
                orgs.newEnvironmentVariable('TEST_VARIABLE') {
                  value: "TESTVALUE",
                },
              ],
            },
          ]
        }
      ]
    }
    ```
