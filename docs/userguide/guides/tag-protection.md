# Protecting tags and releases

Release tags identify the code that was released. If a tag can be moved or deleted, users who download a release
later might get different code than what was reviewed, tested or signed. This guide shows how to protect tags with
rulesets and how to make releases immutable.

!!! note

    GitHub retired tag protection rules and migrated them to tag rulesets, see the
    [GitHub changelog](https://github.blog/changelog/2023-10-18-migrate-tag-protections-to-repository-rules/).
    Otterdog does not support tag protection rules, use rulesets with `target: "tag"` instead.

## Prevent tags from being moved or deleted

The following ruleset allows users with write access to create tags, but nobody can move or delete them
afterwards:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') {
      rulesets: [
        orgs.newRepoRuleset('tags') {
          target: "tag",
          include_refs+: [
            "~ALL",
          ],
          allows_creations: true,
          allows_updates: false, // (1)!
          required_pull_request: null, // (2)!
          required_status_checks: null,
        },
      ],
    },
  ],
}
```

1. Deletions and force pushes are blocked by default (`allows_deletions` and `allows_force_pushes` are `false`).
2. Pull requests do not apply to tags, and this ruleset does not require status checks.

For tag rulesets, `include_refs` accepts `~ALL` or patterns of the form `refs/tags/<pattern>`, see
[Ref Matcher](../../reference/organization/repository/ref-matcher.md).

## Restrict who can create release tags

To ensure that releases are only created by the release process, restrict the creation of release tags to a
release app or a team of release managers:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') {
      rulesets: [
        orgs.newRepoRuleset('release-tags') {
          target: "tag",
          include_refs+: [
            "refs/tags/v*",
          ],
          allows_creations: false,
          allows_updates: false,
          bypass_actors+: [
            "my-release-app",
            "@my-org/release-managers",
          ],
          required_pull_request: null,
          required_status_checks: null,
        },
      ],
    },
  ],
}
```

!!! warning

    With `allows_creations: false` and no bypass actor, nobody can create matching tags, which blocks every
    release. If tags are created by a workflow, make sure that the identity used by the workflow is allowed to
    create them, e.g. by using a token of a GitHub App that is listed as bypass actor.

Bypass actors can also move or delete the matching tags. Combine both rulesets if tags must stay unchanged for
everybody: since all matching rulesets apply, the first ruleset still blocks updates and deletions for the
bypass actors of the second one.

## Make releases immutable

When a release is immutable, its tag cannot be moved or deleted while the release exists, and its assets cannot
be modified or deleted. Immutability only applies to releases published after it has been enabled, see
[Immutable releases](https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/immutable-releases).

Immutable releases can be enforced for some or all repositories of an organization, or enabled per repository:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    immutable_releases_enforced_repositories: "selected",
    immutable_releases_selected_repositories+: [
      "my-library",
    ],
  },
  _repositories+:: [
    orgs.newRepo('my-library'),
    orgs.newRepo('my-tool') {
      immutable_releases_enabled: true,
    },
  ],
}
```

When the organization enforces immutable releases for a repository, the repository setting is ignored, see
[Organization settings take precedence](inheritance.md#organization-settings-take-precedence). These settings are
only managed if the default configuration of your organization defines them, see
[The default configuration also defines what is managed](inheritance.md#the-default-configuration-also-defines-what-is-managed).

!!! tip "Recommendation"

    Protect release tags with a ruleset in every repository that publishes releases. Immutable releases
    additionally protect the release assets, but only for releases published after enabling them, while a tag
    ruleset protects all matching tags, with or without a release.

## Deploy only from tags

To ensure that deployment credentials are only available to workflows that run for a release tag, restrict the
environment used for publishing to tags, see [Deployment environments](environments.md).
