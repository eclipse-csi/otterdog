In order to remove existing resources from a given GitHub organization, the declared resources just have
to be deleted from the jsonnet configuration file.

## Removal of a webhook

For example, we already have a GitHub organization `testorg` that has a webhook as defined like that:

``` jsonnet
orgs.newOrg('testorg') {
  ...
  webhooks+: [
    orgs.newOrgWebhook('https://ci.my.org/testorg/github-webhook/') {
      events+: [
        "create",
        "delete",
        "organization",
        "pull_request",
        "pull_request_review_comment",
        "push",
        "repository"
      ],
      ...
    },
  ],
}
```

In order to remove this webhook, simply delete its definition from the file:

``` diff
orgs.newOrg('testorg') {
  ...
  webhooks+: [
-    orgs.newOrgWebhook('https://ci.my.org/testorg/github-webhook/') {
-      events+: [
-        "create",
-        "delete",
-        "organization",
-        "pull_request",
-        "pull_request_review_comment",
-        "push",
-        "repository"
-      ],
-      ...
-    },
  ],
}
```
