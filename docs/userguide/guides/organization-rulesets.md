# Organization-wide rulesets

A repository ruleset protects the branches of a single repository. An
[organization ruleset](../../reference/organization/ruleset.md) applies the same rules to several repositories,
selected by their name, and is maintained in a single place: administrators of a repository can see it, but not
change or remove it. This guide shows how to define a baseline for all repositories and how to target some of them.

!!! note

    GitHub provides organization rulesets with GitHub Team and GitHub Enterprise, see
    [Availability by GitHub plan](rulesets-vs-branch-protection.md#availability-by-github-plan). Otterdog currently
    only accepts them for organizations on the `enterprise` plan, `validate` reports them as error for other plans.
    The rules that otterdog supports are the same as for repository rulesets, see
    [Otterdog specifics](rulesets-vs-branch-protection.md#otterdog-specifics).

## Protect the default branch of all repositories

The following ruleset blocks force pushes and deletions of the default branch in all repositories of the
organization, except sandboxes:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    plan: "enterprise", // (1)!
  },
  rulesets+: [
    orgs.newOrgRuleset('default-branch-baseline') {
      include_repo_names+: [
        "~ALL",
      ],
      exclude_repo_names+: [
        "sandbox-*", // (2)!
      ],
      include_refs+: [
        "~DEFAULT_BRANCH",
      ],
      required_pull_request: null, // (3)!
      required_status_checks: null,
    },
  ],
  _repositories+:: [
    orgs.newRepo('my-repo'),
    orgs.newRepo('sandbox-experiments'),
  ],
}
```

1. Read-only property that reflects the billing plan of the organization, see the note above.
2. Repository names are matched with the [fnmatch syntax](../../reference/organization/repo-name-matcher.md),
   `~ALL` matches all repositories, including the ones created later. `validate` warns about patterns that do not
   match any repository, e.g. after a repository has been renamed.
3. The baseline only blocks force pushes and deletions, which `orgs.newOrgRuleset()` blocks by default. Requiring
   pull requests and status checks is left to the rulesets of the repositories, as they differ between
   repositories.

!!! tip "Recommendation"

    Start with a baseline that every repository can follow, e.g. blocking force pushes and deletions of the default
    branch, and add stricter rules in the rulesets of the repositories that need them.

## Target repositories by name

To apply stricter rules to a group of repositories, select them by a naming convention, e.g. all libraries:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    plan: "enterprise",
  },
  rulesets+: [
    orgs.newOrgRuleset('libraries') {
      include_repo_names+: [
        "lib-*",
      ],
      protect_repo_names: true, // (1)!
      include_refs+: [
        "~DEFAULT_BRANCH",
      ],
      required_pull_request+: {
        required_approving_review_count: 1,
      },
      required_status_checks: null,
    },
  ],
  _repositories+:: [
    orgs.newRepo('lib-core'),
    orgs.newRepo('lib-cli'),
  ],
}
```

1. A repository could otherwise leave the ruleset by being renamed. With `protect_repo_names`, only the bypass
   actors of the ruleset can rename the targeted repositories.

Otterdog only selects repositories by name: targeting repositories by
[custom properties](organization-settings.md#classify-repositories-with-custom-properties), which GitHub supports,
cannot be configured with otterdog.

## Combine organization and repository rulesets

All rulesets that target a branch apply together, whether they are defined by the organization or by the
repository: when several rulesets configure the same rule, the most restrictive one applies, see
[About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets#about-rule-layering).
A repository ruleset can therefore add rules to an organization ruleset, but not relax it. An example combining
both is shown in [Rulesets or branch protection rules](rulesets-vs-branch-protection.md).

Bypass actors of a ruleset are only exempted from the rules of this ruleset: a release app that must push to the
default branch of all repositories has to be a bypass actor of every ruleset that blocks it.

## Prepare a ruleset before enforcing it

`enforcement` controls whether the rules of a ruleset are enforced:

- `active`: the rules are enforced
- `disabled`: the ruleset exists but is not enforced, e.g. while it is being prepared
- `evaluate`: the rules are not enforced, but GitHub reports which pushes and merges would violate them, see
  [Managing rulesets](https://docs.github.com/en/organizations/managing-organization-settings/managing-rulesets-for-repositories-in-your-organization).
  Only available with GitHub Enterprise.

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    plan: "enterprise",
  },
  rulesets+: [
    orgs.newOrgRuleset('linear-history') {
      enforcement: "disabled",
      include_repo_names+: [
        "~ALL",
      ],
      include_refs+: [
        "~DEFAULT_BRANCH",
      ],
      requires_linear_history: true,
      required_pull_request: null,
      required_status_checks: null,
    },
  ],
}
```

!!! info "Organization policy"

    An organization ruleset immediately applies to many repositories. Announce new rules to the maintainers of the
    repositories before enforcing them, and check that their workflows, e.g. release workflows pushing to protected
    branches, still work.
