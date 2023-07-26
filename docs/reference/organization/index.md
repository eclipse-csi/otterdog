This resource represents a GitHub organization with all supported settings and nested resources.
The following settings and nested resources are currently supported:

1. [Organization Settings](settings.md)
2. [Organization Webhooks](webhook.md)
3. [Organization Secrets](secret.md)
4. [Repositories](repository/index.md)

=== "jsonnet"
    ```jsonnet
    orgs.newOrg('<github-id>') {
        settings+: { ... }, // (1)!
        webhooks+: [ ... ], // (2)!
        secrets+: [ ... ], // (3)!
        _repositories+:: [ ... ], // (4)!
    }
    ```

    1. see [Organization Settings](settings.md)
    2. see [Organization Webhook](webhook.md)
    3. see [Organization Secret](secret.md)
    4. see [Repository](repository/index.md)


!!! note

    Repositories use a slightly different property name (`_repositories+::`) which has mainly technical reasons.
    This syntax allows to override properties for repositories that are already defined in the default configuration.
    See the [Repository](repository/index.md) reference for more details.