Definition of a Codespaces `Secret` on repository level, the following properties are supported:

| Key     | Value                             | Description            | Note |
|---------|-----------------------------------|------------------------|------|
| _name_  | string                            | The name of the secret |      |
| _value_ | [SecretValue](../secret-value.md) | The secret value       |      |

Codespaces secrets are available as environment variables in the codespaces created for the repository, see
[Managing development environment secrets](https://docs.github.com/en/codespaces/managing-codespaces-for-your-organization/managing-development-environment-secrets-for-your-repository-or-organization).
They are managed independently of the [Repository Secrets](secret.md) of GitHub Actions: a Codespaces secret and an
Actions secret can have the same name and different values.

The value should reference a credential provider instead of being written in clear text, see
[SecretValue](../secret-value.md).

## Jsonnet Function

``` jsonnet
orgs.newRepoCodespacesSecret('<name>') {
  <key>: <value>
}
```

## Validation rules

- a `name` that is not uppercase triggers an error, as GitHub normalizes secret names to uppercase
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
          codespaces_secrets+: [
            orgs.newRepoCodespacesSecret('REGISTRY_TOKEN') {
              value: "pass:path/to/secret",
            },
          ],
        }
      ]
    }
    ```
