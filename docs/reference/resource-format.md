---
hide:
  - toc
---

The infrastructure configuration of a GitHub organization is stored in [jsonnet](https://jsonnet.org/) format.

## Jsonnet content

The following example illustrates the basic structure used by otterdog:

``` jsonnet linenums="1" hl_lines="1 3 5 8 15 19"

local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet'; // (1)!

orgs.newOrg('adoptium') { // (2)!
  settings+: {
    blog: "https://adoptium.net", // (3)!
    ...
  },
  webhooks+: [ // (4)!
    orgs.newOrgWebhook('https://app.codacy.com/2.0/events/gh/organization') {
      content_type: "json",
      ...
    },
  ],
  ...
  _repositories+:: [ // (5)!
    orgs.newRepo('.github') {
      allow_auto_merge: true,
      ...
      branch_protection_rules: [ // (6)!
        orgs.newBranchProtectionRule('main'),
      ],
    }
  ]
}
```

1. Import of the default configuration
2. Calling a function to create a specific resource (e.g. a GitHub organization) with default values as defined in the default config
3. Overriding properties for a specific resource as defined in the default configuration, e.g. organization settings
4. Extending an array of objects, e.g. webhooks defined on organization level
5. Extending an array of objects that supports overriding objects already defined in the default configuration
6. Nested resources, e.g. branch protection rules

Let's take a closer look at the definition of a function that is defined in the default configuration, e.g. `orgs.newOrg`:

``` jsonnet
local newOrg(id) = {
  github_id: id,
  settings: {
    name: null,
    plan: "free",
    billing_email: "webmaster@eclipse-foundation.org",
    ...
  },
  ...
}
```

It defines a json object with various properties and their respective values, e.g. `.settings.name` = `null`.

### Concatenation

In order to concatenate json objects, jsonnet offers the `+` operator, which we can use to override specific
properties that are already defined by a function while inheriting every other object or value:

``` jsonnet linenums="1" hl_lines="2"
orgs.newOrg('adoptium') {
  settings+: {
    name: "Eclipse Adoptium",
  }
}
```

The resulting json object will inherit all properties defined by the function `orgs.newOrg`, but will override
the specific property `.settings.name` to the value `Eclipse Adoptium`.

``` jsonnet
{
  github_id: "adoptium",
  settings: {
    name: "Eclipse Adoptium",
    plan: "free",
    billing_email: "webmaster@eclipse-foundation.org",
    ...
  },
  ...
}
```

### Replacement

On the contrary, if we would not use the `+` operator but instead use the function like that:

``` jsonnet linenums="1" hl_lines="2"
orgs.newOrg('adoptium') {
  settings: {
    name: "Eclipse Adoptium",
  }
}
```

the resulting json object would not include any properties in `.settings` as the whole nested
structure was replaced:

``` jsonnet
{
  github_id: "adoptium",
  settings: {
    name: "Eclipse Adoptium",
  },
  ...
}
```

!!! warning

    Otterdog will use the `+` operator by default when importing the current live configuration
    of a GitHub organization. In general it is strongly discouraged to remove the `+` operator
    as it might lead to incomplete configurations due to missing properties.
