Definition of a `Secret` on repository level, the following properties are supported:

| Key     | Value                             | Description            | Note |
|---------|-----------------------------------|------------------------|------|
| _name_  | string                            | The name of the secret |      |
| _value_ | [SecretValue](../secret-value.md) | The secret value       |      |

The value should reference a credential provider instead of being written in clear text, see
[SecretValue](../secret-value.md).

## Jsonnet Function

``` jsonnet
orgs.newRepoSecret('<name>') {
  <key>: <value>
}
```

## Validation rules

- redacted secret values (`********`) trigger a validation info and will skip the secret during processing

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('OtterdogTest') {
      ...
      _repositories+:: [
        ...
        orgs.newRepo('test-repo') {
          ...
          secrets+: [
            orgs.newRepoSecret('TEST_SECRET') {
              value: "pass:path/to/secret",
            },
          ],
        }
      ]
    }
    ```
