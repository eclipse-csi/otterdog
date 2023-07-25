This resource represents a GitHub organization with all supported settings and nested resources.
The following settings and nested resources are currently supported:

1. [organization settings](organization-settings.md)
2. [organization webhooks](organization-webhook.md)
3. [organization secrets](organization-secret.md)
4. [repositories](repository.md)

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


!!! note

    Repositories use a slightly different property name (`_repositories+::`) which has mainly technical reasons.
    This syntax allows to override properties for repositories that are already defined in the default configuration.
    See the [Repository](repository.md) reference for more details.