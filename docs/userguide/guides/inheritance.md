# Inherited and explicit values

Every value that otterdog applies to GitHub comes either from the configuration file of your organization or from
the default configuration that this file imports. Knowing where a value comes from explains most surprises when
reviewing the output of a `plan` operation.

## Where values come from

A value of a resource is determined in the following order:

1. **The default configuration** defines a function for each resource type, e.g. `orgs.newRepo` or
   `orgs.newBranchProtectionRule`. Each function returns an object with a default value for every supported
   property. The default configuration to use is set by `base_template` in the `otterdog.json` file, see
   [Default configuration](../../operating_otterdog/setup.md#default-configuration).
2. **The configuration of your organization** overrides the properties that should differ from the defaults.
   These are the *explicit* values, all other values are *inherited*.
3. **Organization settings** can take precedence over repository settings, see
   [Organization settings take precedence](#organization-settings-take-precedence).

In the following example, `has_wiki` is explicit, while all other properties of the repository, e.g.
`delete_branch_on_merge` or `secret_scanning`, are inherited from `orgs.newRepo`:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') {
      has_wiki: false,
    },
  ],
}
```

To see the values that actually apply, use the following operations:

- [`show-default`](../../reference/operations/index.md) displays the default configuration for an organization
- `show` displays the complete configuration of an organization, with all inherited values resolved
- `canonical-diff` compares a configuration with the canonical form that `import` would write, which reveals
  for example explicit values that are identical to the inherited ones

## The default configuration also defines what is managed

The default configuration does not only provide default values. Otterdog only retrieves, compares and applies the
resource types and organization settings that the default configuration defines:

- an organization setting is only managed if its key is present in the default organization settings
- a resource type, e.g. teams, custom roles or repositories, is only managed if the default configuration provides
  the corresponding function
- team permissions of repositories are only managed if the default repository defines `team_permissions`, see
  [Team Permissions](../../reference/organization/repository/index.md#team-permissions)

As a consequence, adding a key or a function to the default configuration makes otterdog start managing it for
every organization that uses this default configuration. Run a `plan` for all affected organizations before
updating the default configuration.

## Imported configurations only contain differences

The `import` operation only writes the properties whose live value differs from the default configuration. For an
organization that already existed before using otterdog, the imported file usually contains many explicit values,
e.g. `allow_update_branch: false` or `delete_branch_on_merge: false`. Such values describe the state of the
repository at the time of the import, not necessarily a deliberate choice.

!!! tip "Recommendation"

    Before copying a setting from an existing configuration to another repository, check whether it is still
    intended. Removing an explicit value that matches the needs of the repository makes it inherit future
    improvements of the default configuration.

## Extending or replacing values

As explained in [Resource Format](../../reference/resource-format.md), the `+` operator extends the inherited value,
while omitting it replaces the inherited value. For nested objects like `settings` or `workflows`, always use `+:`,
otherwise all other inherited properties of the object are lost.

For lists, both forms are valid but have different effects:

- `<key>+: [...]` appends entries to the inherited list
- `<key>: [...]` replaces the inherited list

This matters for lists that are not empty in your default configuration, e.g. required status checks, bypass actors,
security managers or webhook events. In the following example, the function `newRule` stands for a branch protection
rule as it could be defined by the default configuration of your organization:

``` jsonnet
// a rule as it could be defined by the default configuration of your organization
local newRule(pattern) = orgs.newBranchProtectionRule(pattern) {
  required_approving_review_count: 1,
  required_status_checks: [
    "license-check",
  ],
};

orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('extended-repo') {
      branch_protection_rules: [
        newRule('main') {
          required_status_checks+: [ // (1)!
            "build",
          ],
        },
      ],
    },
    orgs.newRepo('replaced-repo') {
      branch_protection_rules: [
        newRule('main') {
          required_status_checks: [ // (2)!
            "build",
          ],
        },
      ],
    },
  ],
}
```

1. Required status checks: `license-check` and `build`.
2. Required status checks: only `build`, the inherited `license-check` is no longer required.

!!! tip "Recommendation"

    Use `+:` unless you deliberately want to drop inherited entries. If you do, add a comment that explains why,
    as reviewers cannot see the inherited entries in the diff of a pull request.

## Always use the functions of the default configuration

Create resources with the functions of the default configuration, e.g. `orgs.newBranchProtectionRule`, instead of
writing plain objects. A plain object only contains the properties that are written in it: all other properties are
not set, so otterdog does not manage them and the configuration no longer describes the actual protection.

``` diff
 branch_protection_rules: [
-  {
-    pattern: "main",
-    requires_pull_request: true,
-    required_approving_review_count: 1,
-  },
+  orgs.newBranchProtectionRule('main') {
+    required_approving_review_count: 1,
+  },
 ],
```

Similarly, use `orgs.extendRepo('<name>')` instead of `orgs.newRepo('<name>')` to change a repository that is
already defined by the default configuration, see [Repository](../../reference/organization/repository/index.md#jsonnet-function).
Using `orgs.newRepo` would reset all properties that the default configuration customized for this repository.

## Organization settings take precedence

Some organization settings restrict what repositories can configure, as GitHub does. When an organization setting
is more restrictive, otterdog ignores the repository setting and reports it during validation:

| Organization setting                                                         | Ignored repository setting                       |
|------------------------------------------------------------------------------|--------------------------------------------------|
| `web_commit_signoff_required: true`                                          | `web_commit_signoff_required`                    |
| `workflows.default_workflow_permissions: "read"`                             | `workflows.default_workflow_permissions`         |
| `workflows.actions_can_approve_pull_request_reviews: false`                  | `workflows.actions_can_approve_pull_request_reviews` |
| `workflows.allowed_actions` more restrictive than the repository setting     | `workflows.allowed_actions` and related settings |
| `workflows.enabled_repositories: "none"`, or `"selected"` without the repository | `workflows.enabled`                          |
| `has_organization_projects: false`                                           | `has_projects`                                   |
| `immutable_releases_enforced_repositories` includes the repository           | `immutable_releases_enabled`                     |

See [Organization Settings](../../reference/organization/settings.md) and
[Repository](../../reference/organization/repository/index.md) for a description of these settings.

!!! note

    A repository setting that is ignored remains in the configuration and takes effect as soon as the organization
    setting allows it. Remove such settings if they are not intended anymore, otherwise relaxing the organization
    setting later might have unexpected effects.

## Updating the default configuration

Changing a default value affects every resource that does not override it, in every organization that uses the
default configuration.

!!! tip "Recommendation"

    Reference a released version of the default configuration in `base_template`, e.g. `...@v1.2.0` instead of
    `...@main`. Before switching to a newer version, review its changes and run a `plan` operation for the
    affected organizations to see their impact.
