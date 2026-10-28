Definition of a Dependabot `Secret` on organization level, the following properties are supported:

| Key                     | Value                          | Description                                    | Note                                                 |
|-------------------------|--------------------------------|------------------------------------------------|------------------------------------------------------|
| _name_                  | string                         | The name of the secret                         |                                                      |
| _selected_repositories_ | list[string]                   | List of repositories that can use the secret   | only applicable if `visibility` is set to `selected` |
| _value_                 | [SecretValue](secret-value.md) | The secret value                               |                                                      |
| _visibility_            | string                         | Controls which repositories can use the secret | `public`, `private` or `selected`                    |

Dependabot secrets are used by Dependabot, e.g. to access private registries, and are the only secrets available to
workflows triggered by Dependabot, see
[Configuring access to private registries for Dependabot](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/configure-access-to-private-registries).
They are managed independently of the [Organization Secrets](secret.md) of GitHub Actions: a Dependabot secret and
an Actions secret can have the same name and different values.

The value should reference a credential provider instead of being written in clear text, see
[SecretValue](secret-value.md).

## Jsonnet Function

``` jsonnet
orgs.newOrgDependabotSecret('<name>') {
  <key>: <value>
}
```

## Validation rules

- a `name` that is not uppercase triggers an error, as GitHub normalizes secret names to uppercase
- redacted secret values (`********`) trigger a validation info and will skip the secret during processing
- specifying a non-empty list of `selected_repositories` while `visibility` is not set to `selected` triggers a warning

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('OtterdogTest') {
      ...
      dependabot_secrets+: [
        orgs.newOrgDependabotSecret('REGISTRY_TOKEN') {
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
