Definition of a `Secret` on repository level, the following properties are supported:

| Key                     | Value          | Description                                    | Note |
|-------------------------|----------------|------------------------------------------------|------|
| _name_                  | string         | The name of the secret                         |      |
| _value_                 | string         | The secret value                               |      |

The secret value can be resolved via a credential provider. The supported format is `<credential_provider>:<provider specific data>`.

- Bitwarden: `bitwarden:<bitwarden item id>@<custom_field_key>`

    ``` json
    "secret": "bitwarden:118276ad-158c-4720-b68d-af8c00fe3481@secret"
    ```

- Pass: `pass:<path/to/secret>`

    ``` json
    "secret": "pass:path/to/repo/secret"
    ```

!!! note

    After executing an `import` operation, the secret will be set to `********` as GitHub will not disclose the
    secret value anymore via its API. You will need to update the configuration with the real secret value, either
    by entering the secret value (not advised), or referencing it via a credential provider.

    Secrets which have a redacted value defined will be skipped during processing.

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
