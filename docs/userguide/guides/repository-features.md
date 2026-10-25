# Repository features and metadata

Repositories come with features that a project may or may not use, e.g. issues, a wiki, projects or discussions,
and with metadata that help to find them, e.g. a description and topics. This guide shows how to enable the
features that a project uses, how to set up discussions for the whole organization and how to describe repositories.

## Enable only the features that are used

A feature that nobody looks at, e.g. a wiki that is not maintained or issues that are tracked elsewhere, misleads
users. The following repository tracks its issues and discussions on GitHub, but keeps its documentation in the
repository itself:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') {
      has_issues: true,
      has_discussions: true,
      has_wiki: false,
      has_projects: false,
    },
  ],
}
```

| Setting           | Feature                                       | Notes                                                                 |
|-------------------|-----------------------------------------------|-----------------------------------------------------------------------|
| `has_issues`      | issues                                        |                                                                       |
| `has_discussions` | discussions                                   | the repository used for the discussions of the organization keeps them |
| `has_wiki`        | wiki                                          | private repositories require a paid GitHub plan                       |
| `has_projects`    | projects of the repository                    | ignored if the organization disables `has_organization_projects`      |

Disabling a feature hides it but does not delete its content: issues, wiki pages and discussions come back when
the feature is enabled again.

## Discussions for the whole organization

Organization discussions are hosted in a repository of the organization, usually the `.github` repository, see
[Enabling GitHub Discussions for your organization](https://docs.github.com/en/organizations/managing-organization-settings/enabling-or-disabling-github-discussions-for-an-organization):

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    has_discussions: true,
    discussion_source_repository: "my-org/.github", // (1)!
  },
  _repositories+:: [
    orgs.newRepo('.github') {
      has_discussions: true, // (2)!
    },
  ],
}
```

1. The repository in the format `<organization>/<repository>`. Enabling `has_discussions` without it is reported
   as error by `validate`.
2. The source repository must keep discussions enabled, disabling them is reported as error.

`readers_can_create_discussions` controls whether users with read access can start discussions in the repositories
of the organization, otherwise only users with at least triage permission can. Users with read access can comment
on discussions in both cases.

!!! note

    The discussion settings of the organization can only be read and changed through the GitHub web interface,
    otterdog applies them with the credentials of a user that can log in to GitHub, see
    [Organization settings and member privileges](organization-settings.md#restrict-what-members-can-do).

## Describe repositories

A description, a homepage and topics help users to find a repository and to understand its purpose. Topics are
also used by the search of GitHub:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-library') {
      description: "A library to parse configuration files",
      homepage: "https://my-library.example.org",
      topics+: [
        "configuration",
        "parser",
        "java",
      ],
    },
  ],
}
```

GitHub limits these metadata, `validate` reports the following as error:

- a description longer than 350 characters
- more than 20 topics
- a topic with other characters than lower-case letters, numbers and `-`, e.g. `GitHub Actions` instead of
  `github-actions`

!!! tip "Recommendation"

    Describe every active repository, and agree on a set of topics in the organization, e.g. the technologies and
    the components, so that topics group related repositories.

Templates, mirrors, forks and websites are covered in [Common repository patterns](repository-patterns.md).
