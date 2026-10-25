# Reusing configuration with Jsonnet

When many repositories share the same settings, repeating them makes the configuration long and lets the
repositories drift apart over time. As the configuration is written in [Jsonnet](https://jsonnet.org/), common
settings can be defined once and reused.

## Functions for families of repositories

A local function can define the settings of a family of repositories. Each repository can still override them:

``` jsonnet
local newLibraryRepo(name) = orgs.newRepo(name) {
  dependabot_security_updates_enabled: true,
  private_vulnerability_reporting_enabled: true,
  rulesets: [
    orgs.newRepoRuleset('default-branch') {
      include_refs+: [
        "~DEFAULT_BRANCH",
      ],
      required_pull_request+: {
        required_approving_review_count: 1,
      },
      required_status_checks: null,
    },
  ],
};

orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    newLibraryRepo('library-a'),
    newLibraryRepo('library-b') {
      description: "Library B", // (1)!
    },
  ],
}
```

1. Settings can be added or overridden as for any other repository.

## Parameterized protections

Functions can take parameters, and Jsonnet supports conditions and list comprehensions to compute values:

``` jsonnet
local defaultBranchRuleset(checks=[]) = orgs.newRepoRuleset('default-branch') {
  include_refs+: [
    "~DEFAULT_BRANCH",
  ],
  required_pull_request+: {
    required_approving_review_count: 1,
  },
  required_status_checks:
    if std.length(checks) > 0
    then orgs.newStatusChecks() { status_checks: checks }
    else null,
};

local maintenanceBranches = ["1.x", "2.x"];

orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') {
      rulesets: [
        defaultBranchRuleset(["build", "test"]),
        orgs.newRepoRuleset('maintenance-branches') {
          include_refs+: [
            "refs/heads/maintenance/%s" % branch
            for branch in maintenanceBranches
          ],
          required_pull_request+: {
            required_approving_review_count: 1,
          },
          required_status_checks: null,
        },
      ],
    },
    orgs.newRepo('my-docs') {
      rulesets: [
        defaultBranchRuleset(),
      ],
    },
  ],
}
```

See the [Jsonnet standard library](https://jsonnet.org/ref/stdlib.html) for the available functions.

## Organization-specific defaults

If most repositories of an organization deviate from the default configuration in the same way, the functions of the
default configuration can be overridden at the top of the configuration file:

``` jsonnet
local defaults = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet'; // (1)!

local orgs = defaults + {
  newRepo(name):: defaults.newRepo(name) {
    dependabot_security_updates_enabled: true,
  },
};

orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo'),
  ],
}
```

1. Keep the `import` statement of your configuration file, which depends on the default configuration in use.

!!! note

    The override only applies to the calls in your configuration file. Resources that the default configuration
    itself creates, e.g. repositories defined by `orgs.newOrg`, still use the original functions. If the same
    deviation applies to several organizations, change the default configuration instead.

## Trade-offs

!!! warning

    The `import` operation writes the configuration in its canonical form: local functions, variables and comments
    are lost, and only the previous file is kept as backup with the `.bak` extension. Once a configuration uses
    functions, update it by editing it rather than by importing it again.

- **Review**: the diff of a pull request shows the change of a function, not its effect on every repository. Review
  the output of `plan`, or the automated comment on the pull request, to see the actual changes.
- **Canonical form**: `canonical-diff` reports the differences between the configuration and its canonical form,
  which includes every use of a function.
- **Readability**: a few well-named functions make a large configuration easier to read, deeply nested functions
  make it harder. Prefer simple functions with a clear purpose, and document their parameters with a comment.
- **Default branch**: to protect the default branch, prefer `~DEFAULT_BRANCH` in a ruleset over referring to the
  `default_branch` property of the repository with `self`.
