Definition of a `Webhook` on organization level, the following properties are supported:

| Key            | Value          | Description                                                                                                       | Notes                                                                                                   |
|----------------|----------------|-------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| _url_          | string         | The payload url to which a POST request will be sent when the webhook gets triggered                              |                                                                                                         |
| _active_       | boolean        | If the webhook is active                                                                                          |                                                                                                         |
| _aliases_      | list[string]   | List of webhook alias urls, can be used to change the url of a webhook without re-creating the webhook as a whole | read-only property                                                                                      |
| _content_type_ | string         | The content type the webhook shall use                                                                            | `json` or `form`                                                                                        |
| _events_       | list[string]   | List of events that trigger the webhook                                                                           | [supported events](https://docs.github.com/en/webhooks-and-events/webhooks/webhook-events-and-payloads) |
| _insecure_ssl_ | string         | If the webhook uses insecure ssl connections                                                                      | `0` or `1`                                                                                              |
| _secret_       | string or null | The secret the webhook shall use if any                                                                           |                                                                                                         |

The secret value can be resolved via a credential provider. The supported format is `<credential_provider>:<provider specific data>`.

- Bitwarden: `bitwarden:<bitwarden item id>@<custom_field_key>`

    ``` json
    "secret": "bitwarden:118276ad-158c-4720-b68d-af8c00fe3481@webhook_secret"
    ```

- Pass: `pass:<path/to/secret>`

    ``` json
    "secret": "pass:path/to/org/webhook_secret"
    ```

!!! note

    After executing an `import` operation, the secret will be set to `********` as GitHub will only send redacted
    secrets. You will need to update the configuration with the real secret value, either by entering the secret
    value (not advised), or referencing it via a credential provider.

    Webhooks which have a redacted secret defined will be skipped during processing.

## Jsonnet Function

``` jsonnet
orgs.newOrgWebhook('<url>') {
  <key>: <value>
}
```

## Validation rules

- redacted secrets (`********`) trigger a validation info and will skip the webhook during processing
- `content_type` must either be `json` or `form`
- `insecure_ssl` must either be `0` (disabled) or `1` (enabled)

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('adoptium') {
      ...
      webhooks+: [
        orgs.newOrgWebhook('https://app.codacy.com/2.0/events/gh/organization') {
          content_type: "json",
          events+: [
            "meta",
            "organization",
            "repository"
          ],
          secret: "pass:path/to/my/webhook/secret",
        },
      ],
      ...
    }
    ```
