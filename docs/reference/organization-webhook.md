---
hide:
  - toc
---

### Webhooks

| Field        | Type             | Description                                                                             |
|--------------|------------------|-----------------------------------------------------------------------------------------|
| active       | boolean          | If the webhook is active                                                                |
| aliases      | list[string]     | List of webhook alias urls, need to add previous url when changing the url of a webhook |
| events       | array of strings | List of events that trigger the webhook                                                 |
| url          | string           | Url the webhook should access                                                           |
| content_type | string           | The content type the webhook shall use                                                  |
| insecure_ssl | string           | If the webhook uses insecure ssl connections, either "0" or "1"                         |
| secret       | string or null   | The secret the webhook shall use if any                                                 |

The secret value can be resolved using a credential provider. The supported format is 
`<credential_provider>:<provider specific data>`:

* Bitwarden: `bitwarden:<bitwarden item id>@<custom_field_key>`
* Pass: `pass:<path/to/secret>`

Examples:

```json
{
  "secret": "bitwarden:118276ad-158c-4720-b68d-af8c00fe3481@webhook_secret"
}
```

```json
{
  "secret": "pass:myorg/mywebhook_secret"
}
```

Note: After executing an `import` operation, the secret will be set to `********` as GitHub will only send redacted
secrets. You will need to update the definition file with the real secret value, either by entering the secret
value (not advised), or referencing it via a credential provider.
