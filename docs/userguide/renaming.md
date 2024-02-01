In general, changing the unique identifier (e.g. the name of a repo, url of a webhook) of a resource
in the configuration will result in the situation that the existing resource with the identifier will
get deleted and a new resource with the new identifier gets created. See an example of the output of
a `plan` operation where the `url` of a webhook has been changed:

``` diff
- remove repo_webhook[url="https://www.example.org", repository="test-repo5"] {
-   active                                                   = true
-   content_type                                             = "form"
-   events                                                   = [
-     "push"
-   ],
-   insecure_ssl                                             = "0"
-   url                                                      = "https://www.example.org"
- }

+ add repo_webhook[url="https://www.example.org/webhook", repository="test-repo5"] {
+   active                                                   = true
+   content_type                                             = "form"
+   events                                                   = [
+     "push"
+   ],
+   insecure_ssl                                             = "0"
+   url                                                      = "https://www.example.org/webhook"
+ }
```

In some cases, re-creation of a resource is not an idempotent operation (especially in the case of a Repository)
as some content of the resource would be lost in the process. Some resources support a list of `aliases`, which
allows to specify previous identifiers of the same resource that will be used to associate current live resources
with entries in the configuration.

After the changes have been applied, the `aliases` property can be safely remove as it is not needed anymore,
but it can be left for traceability to know what the previous identifiers or a resource have been.

## Supported resources

- [Organization Webhook](../reference/organization/webhook.md)
- [Repository](../reference/organization/repository/index.md)
- [Repository Webhook](../reference/organization/repository/webhook.md)

## Example usage

Taking the example from above, let's specify the previous identifier of the webhook in the `aliases` property:

=== "Webhook"
    ``` jsonnet
    webhooks: [
        orgs.newRepoWebhook('https://www.example.org/webhook') {
            aliases: ['https://www.example.org'],
            events+: [
                "push"
            ],
        },
    ],
    ```

The result of the `plan` operation for the Webhook would look like this now:

``` diff
~ repo_webhook[url="https://www.example.org", repository="xxxxxxx"] {
~   url                 = "https://www.example.org" -> "https://www.example.org/webhook"
~ }
```

Analogously, the `aliases` property can also be specified for a repository, e.g. to rename an existing
repository named `oldreponame` to `newreponame`:

=== "Repository"
    ``` jsonnet
    orgs.newOrg('testorg') {
      ...
      _repositories+:: [
        ...
        orgs.newRepo('newreponame') {
          aliases: ['oldreponame'],
          allow_auto_merge: true,
          allow_merge_commit: false,
          allow_update_branch: false,
          dependabot_alerts_enabled: false,
          web_commit_signoff_required: false,
          branch_protection_rules: [
            orgs.newBranchProtectionRule('main'),
          ],
        },
    }
    ```
