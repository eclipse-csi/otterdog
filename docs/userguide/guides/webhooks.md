# Webhooks

Webhooks notify external services, e.g. a CI server or a documentation builder, about events. An
[organization webhook](../../reference/organization/webhook.md) receives the events of all repositories, a
[repository webhook](../../reference/organization/repository/webhook.md) only those of its repository.

## Configure a secure webhook

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  webhooks+: [
    orgs.newOrgWebhook('https://ci.example.org/github-webhook/') {
      content_type: "json",
      events+: [
        "pull_request",
        "push",
      ],
      secret: "pass:path/to/ci-webhook-secret", // (1)!
    },
  ],
  _repositories+:: [
    orgs.newRepo('my-repo') {
      webhooks+: [
        orgs.newRepoWebhook('https://docs.example.org/hooks/my-repo') {
          content_type: "json",
          events+: [
            "push",
          ],
          secret: "pass:path/to/docs-webhook-secret",
        },
      ],
    },
  ],
}
```

1. A reference to a credential provider, see [Secrets and variables](secrets-and-variables.md#reference-secret-values-never-write-them).

!!! tip "Recommendation"

    Following the [best practices for using webhooks](https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks):

    - set a secret, so that the receiver can verify that a delivery comes from GitHub
    - keep SSL verification enabled (`insecure_ssl: "0"`, the default) and use an `https` URL
    - subscribe only to the events that the service needs

## Change the URL of a webhook

The URL identifies a webhook: changing it in the configuration deletes the webhook and creates a new one. To update
the existing webhook instead, list the previous URL in `aliases`, see [Renaming of Resources](../renaming.md):

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  webhooks+: [
    orgs.newOrgWebhook('https://ci.example.org/hooks/github') {
      aliases: [
        "https://ci.example.org/github-webhook/", // (1)!
      ],
      content_type: "json",
      events+: [
        "pull_request",
        "push",
      ],
      secret: "pass:path/to/ci-webhook-secret",
    },
  ],
}
```

1. The previous URL: the existing webhook keeps its deliveries and settings, and only its URL is updated. The alias
   can be removed once the change has been applied.

## Pause a webhook

To stop the deliveries temporarily, e.g. while the receiving service is migrated, set `active: false` instead of
removing the webhook: its URL, events and secret are kept, and deliveries resume once it is active again.

## Secrets after an import

After an `import`, the secret of a webhook is `********` and the webhook is skipped until the value is replaced by a
reference to a credential provider. A rotated secret must be sent again explicitly. Both are described in
[SecretValue](../../reference/organization/secret-value.md).

## Remove webhooks that are not used anymore

Webhooks often outlive the service they were created for. A webhook pointing to a service that no longer exists
fails on every delivery and sends the events of your repositories to a domain that you might not control anymore.
Check the recent deliveries of webhooks in the GitHub web interface and remove the webhooks that are not used
anymore from the configuration.

!!! note

    Integrations that serve many repositories are often better implemented as GitHub Apps, which receive events
    through their own webhook and request only the permissions they need. The installation of GitHub Apps cannot be
    managed with otterdog, see [Unsupported Features](../unsupported.md).
