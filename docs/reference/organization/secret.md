Definition of a `Secret` on organization level, the following properties are supported:

| Key                     | Value          | Description                                    | Note                                                 |
|-------------------------|----------------|------------------------------------------------|------------------------------------------------------|
| _name_                  | string         | The name of the secret                         |                                                      |
| _selected_repositories_ | list[string]   | List of repositories that can use the secret   | only applicable if `visibility` is set to `selected` |
| _value_                 | string         | The secret value                               |                                                      |
| _visibility_            | string         | Controls which repositories can use the secret | `public`, `private` or `selected`                    |

The secret value can be resolved via a credential provider. The supported format is `<credential_provider>:<provider specific data>`.

- Bitwarden: `bitwarden:<bitwarden item id>@<custom_field_key>`

    ``` json
    "secret": "bitwarden:118276ad-158c-4720-b68d-af8c00fe3481@secret"
    ```

- Pass: `pass:<path/to/secret>`

    ``` json
    "secret": "pass:path/to/org/secret"
    ```

!!! note

    After executing an `import` operation, the secret will be set to `********` as GitHub will not disclose the
    secret value anymore via its API. You will need to update the configuration with the real secret value, either
    by entering the secret value (not advised), or referencing it via a credential provider.

    Secrets which have a redacted value defined will be skipped during processing.

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
