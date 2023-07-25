A GitHub Organization is the main entrypoint.

=== "jsonnet"
    ```jsonnet
    orgs.newOrg('<github-id>') {
        settings+: { ... }, // (1)!
        webhooks+: [ ... ], // (2)!
        secrets+: [ ... ], // (3)!
        _repositories+:: [ ... ], // (4)!
    }
    ```

    1. see [Organization Settings](organization-settings.md)
    2. see [Organization Webhook](organization-webhook.md)
    3. see [Organization Secret](organization-secret.md)
    4. see [Repository](repository.md)

