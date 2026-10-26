# Common repository patterns

This guide collects the settings of recurring kinds of repositories. All properties are described in
[Repository](../../reference/organization/repository/index.md).

## Websites with GitHub Pages

GitHub Pages can be built from a branch (`gh_pages_build_type: "legacy"`) or by a workflow
(`gh_pages_build_type: "workflow"`). In both cases, GitHub creates an environment named `github-pages`, which
should be declared in the configuration, see [Deployment environments](environments.md#github-pages).

The repository named `<organization>.github.io` hosts the website of the organization. GitHub enables Pages for it
automatically, so otterdog requires it to be configured:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-org.github.io') {
      gh_pages_build_type: "legacy",
      gh_pages_source_branch: "main",
      gh_pages_source_path: "/",
      environments+: [
        orgs.newEnvironment('github-pages') {
          deployment_branch_policy: "selected",
          branch_policies+: [
            "main",
          ],
        },
      ],
    },
    orgs.newRepo('my-project') {
      gh_pages_build_type: "workflow",
      gh_pages_cname: "docs.example.org", // (1)!
      environments+: [
        orgs.newEnvironment('github-pages') {
          deployment_branch_policy: "selected",
          branch_policies+: [
            "main",
          ],
        },
      ],
    },
  ],
}
```

1. A custom domain requires DNS records that are configured outside otterdog.

!!! tip "Recommendation"

    When using a custom domain, [verify the domain](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/verifying-your-custom-domain-for-github-pages)
    for the organization to prevent domain takeovers, and keep `gh_pages_https_enforced` enabled.

The organization setting `members_can_create_public_pages` must be enabled for sites to be published.

## The `.github` repository

A repository named `.github` provides
[default community health files](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file),
e.g. `SECURITY.md` or `CONTRIBUTING.md`, for all repositories of the organization that do not define their own. It
is also the usual place for shared workflow templates.

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('.github') {
      description: "Default community health files",
      has_wiki: false,
      has_projects: false,
    },
  ],
}
```

[Blueprints](../../reference/blueprints/index.md) can ensure that such a repository and its files exist in every
organization, e.g. with the [Append Configuration](../../reference/blueprints/append-configuration.md) and
[Required File](../../reference/blueprints/required-file.md) types.

## Read-only mirrors

A mirror of a repository hosted elsewhere should not receive contributions on GitHub:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-mirror') {
      description: "Read-only mirror, contributions are accepted at https://git.example.org/my-project",
      has_issues: false,
      has_projects: false,
      has_wiki: false,
      workflows+: {
        enabled: false,
      },
      rulesets: [
        orgs.newRepoRuleset('read-only') {
          include_refs+: [
            "~ALL",
          ],
          allows_creations: false,
          allows_updates: false,
          allows_deletions: false,
          bypass_actors+: [
            "my-mirror-app",
          ],
          required_pull_request: null,
          required_status_checks: null,
        },
      ],
    },
  ],
}
```

Only the app that synchronizes the mirror can push, see [Protecting branches](branch-protection.md#read-only-branches-and-mirrors).

## Templates and repositories created from a template

- `is_template: true` marks a repository as template.
- `template_repository` creates a new repository from a template. `post_process_template_content` lists files of
  the new repository in which the [Mustache](https://mustache.github.io/) variables `{{org}}` and `{{repo}}` are
  replaced after creation.

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('project-template') {
      is_template: true,
    },
    orgs.newRepo('my-new-project') {
      template_repository: "my-org/project-template",
      post_process_template_content+: [
        "README.md",
      ],
    },
  ],
}
```

Both `template_repository` and `post_process_template_content` are only taken into account when the repository is
created. The `sync-template` operation of the [CLI](../../reference/operations/index.md) synchronizes the content of
repositories created from a template.

## Forks

`forked_repository` creates the repository as a fork of another repository, `fork_default_branch_only` limits the
fork to the default branch. Both are only taken into account during creation, and a repository cannot be created
from a template and as a fork at the same time.

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('upstream-library') {
      forked_repository: "example-owner/upstream-library",
    },
  ],
}
```

## Renaming, archiving and deleting

- **Renaming**: list the previous name in `aliases`, otherwise the repository is deleted and a new one is created,
  see [Renaming of Resources](../renaming.md).
- **Archiving**: `archived: true` makes the repository read-only. Many settings cannot be changed on archived
  repositories, and otterdog ignores them until the repository is unarchived, as well as its branch protection
  rules.
- **Deleting**: removing a repository from the configuration deletes it on GitHub, including its issues, pull
  requests and wiki, when the configuration is applied with deletions enabled. Pull requests that delete resources
  are not merged automatically, but the deletion is applied once they are merged.

!!! warning

    Prefer archiving over deleting: a deleted repository cannot be restored by otterdog, and its URL can be taken by
    a new repository. Transferring a repository to another organization is not supported by otterdog.
