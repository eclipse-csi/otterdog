# GitHub Organization

This resource represents a GitHub organization with all supported settings and nested resources.

=== "jsonnet"
    ```jsonnet
    orgs.newOrg('<project-name>', '<github-id>') {
        settings+: { ... }, // (1)!
        webhooks+: [ ... ], // (2)!
        secrets+: [ ... ], // (3)!
        variables+: [ ... ], // (4)!
        rulesets+: [ ... ], // (5)!
        _repositories+:: [ ... ], // (6)!
    }
    ```

    1. see [Organization Settings](settings.md)
    2. see [Organization Webhook](webhook.md)
    3. see [Organization Secret](secret.md)
    4. see [Organization Variable](variable.md)
    5. see [Organization Ruleset](ruleset.md)
    6. see [Repository](repository/index.md)

!!! note

    Repositories use a slightly different property name (`_repositories+::`) which has mainly technical reasons.
    This syntax allows to override properties for repositories that are already defined in the default configuration.
    See the [Repository](repository/index.md) reference for more details.

## Jsonnet Function

``` jsonnet
orgs.newOrg('<project-name>', <github-id>') {
  <key>: <value>
}
```

## Validation rules

The configuration of a GitHub Organization is considered to be valid if all nested resources are valid.

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('adoptium', 'adoptium') {
      settings+: {
        blog: "https://adoptium.net",
        default_repository_permission: "none",
        description: "The Adoptium Working Group ...",
        name: "Eclipse Adoptium",
        security_managers+: [
          "adoptium-project-leads"
        ],
        twitter_username: "adoptium",
      },
      webhooks+: [
        orgs.newOrgWebhook('https://app.codacy.com/2.0/events/gh/organization') {
          content_type: "json",
          events+: [
            "meta",
            "organization",
            "repository"
          ],
          secret: "********",
        },
      ],
      secrets+: [
        orgs.newOrgSecret('ADOPTIUM_AQAVIT_BOT_TOKEN') {
          value: "pass:bots/adoptium.aqavit/github.com/project-token",
        },
      ],
      variables+: [
        orgs.newOrgVariable('SONAR_USERNAME') {
          value: "xxxxx",
        },
      ],
      _repositories+:: [
        orgs.newRepo('Incubator') {
          allow_update_branch: false,
          dependabot_alerts_enabled: false,
          description: "Adoptium Incubator project",
          web_commit_signoff_required: false,
        },
      ]
    }
    ```
