A Secret Value is the value of a secret on organization, repository or environment level, or the secret of an
organization or repository webhook.

As the configuration is stored in a repository, a secret value should not be written in clear text. Instead, it
references the secret in a credential provider, using the format `<credential_provider>:<provider specific data>`.
Otterdog resolves the reference when applying the configuration.

| Provider        | Format                                              | Example                                                  |
|-----------------|-----------------------------------------------------|----------------------------------------------------------|
| Bitwarden       | `bitwarden:<bitwarden item id>@<custom_field_key>`  | `bitwarden:118276ad-158c-4720-b68d-af8c00fe3481@secret`  |
| Pass            | `pass:<path/to/secret>`                             | `pass:path/to/secret`                                    |
| HashiCorp Vault | `vault:<path/to/secret>/<field>`                    | `vault:path/to/secret/field`                             |

The setup of the credential providers is described in [Credentials](../../operating_otterdog/setup.md#credentials).

## Redacted values

GitHub does not disclose secret values via its API. After executing an `import` operation, secret values are
therefore set to `********`. Resources with such a redacted value are skipped during processing: replace the value
with a reference to a credential provider to manage the resource with otterdog.

## Updating values

As otterdog does not maintain any local state and GitHub does not disclose secret values, otterdog can not detect
that a value changed in the credential provider. Use the `--update-secrets` or `--update-webhooks` options of the
[apply](../operations/apply.md) operation to update them, limited to specific secrets or webhooks with
`--update-filter`.

## Validation rules

- a value that does not reference a supported credential provider triggers a warning
- a redacted value (`********`) triggers a validation info, the resource will be skipped during processing
