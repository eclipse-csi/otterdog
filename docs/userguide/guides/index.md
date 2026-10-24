# Configuration Guides

The guides in this section start from a need, e.g. protecting a release branch or limiting the permissions of
workflows, and explain how to address it with otterdog: which properties to use, what the consequences of each
choice are and which trade-offs to consider. They complement the [Reference](../../reference/index.md), which
documents every supported property, and link to it instead of repeating it.

## How to read the guides

- **Examples are complete and minimal**: each example is a complete organization configuration that only contains
  the properties relevant to the topic. All other properties are inherited from the default configuration. The
  `import` statement at the top of the configuration file is omitted.
- **Examples use the example default configuration**: the values that an example inherits come from the
  [example default configuration](https://github.com/eclipse-csi/otterdog/blob/main/examples/template/otterdog-defaults.libsonnet).
  The default configuration of your organization may define different values, see
  [Inherited and explicit values](inheritance.md).
- **Examples can be tried out**: the link below an example opens it in the Playground of the otterdog dashboard,
  which also lists all examples of these guides, and checks the values of the configuration like otterdog does.
  The link evaluates the example with the example default configuration. The Playground can also evaluate it with
  the default configuration of the otterdog instance, which may define other values, or not provide all of its
  functions.
- **Recommendations and policies are distinguished**: guides mark general recommendations and choices that depend
  on the policy of your organization:

    !!! tip "Recommendation"

        A practice that is recommended in general, usually based on the GitHub documentation.

    !!! info "Organization policy"

        A choice that depends on the requirements, the size or the governance of your organization.

- **GitHub plans matter**: some GitHub features are only available for certain GitHub plans or repository
  visibilities. Otterdog cannot enable a feature that GitHub does not provide for your organization. Guides
  mention the relevant availability and link to the GitHub documentation, which remains the authoritative source.

## Guides

### Fundamentals

| Guide                                                       | Read it when you want to ...                                                                 |
|-------------------------------------------------------------|----------------------------------------------------------------------------------------------|
| [Inherited and explicit values](inheritance.md)             | understand where a value comes from and why a `plan` shows a change                          |
| [Reusing configuration with Jsonnet](reusable-configuration.md) | share settings between many repositories without copying them                            |

### Protecting code

| Guide                                                                          | Read it when you want to ...                                                  |
|--------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| [Protecting branches](branch-protection.md)                                    | protect the default branch or release branches                                |
| [Organization-wide rulesets](organization-rulesets.md)                         | apply the same protection to many repositories                                |
| [Rulesets or branch protection rules](rulesets-vs-branch-protection.md)        | choose between the two mechanisms                                             |
| [Migrating to rulesets](migrating-to-rulesets.md)                              | replace branch protection rules with rulesets without losing protection       |
| [Protecting tags and releases](tag-protection.md)                              | prevent release tags from being moved or deleted                              |

### Security and automation

| Guide                                                   | Read it when you want to ...                                                         |
|---------------------------------------------------------|--------------------------------------------------------------------------------------|
| [Securing GitHub Actions](github-actions.md)            | limit the permissions of workflows and control which actions can run                 |
| [Repository security features](repository-security.md)  | enable secret scanning, Dependabot, code scanning and vulnerability reporting        |
| [Secrets and variables](secrets-and-variables.md)       | provide credentials to workflows without exposing them                               |
| [Deployment environments](environments.md)              | protect deployments and publishing with approvals and branch restrictions            |
| [Webhooks](webhooks.md)                                 | connect external services securely                                                   |

### Organization and access

| Guide                                                                  | Read it when you want to ...                                          |
|------------------------------------------------------------------------|-----------------------------------------------------------------------|
| [Organization settings and member privileges](organization-settings.md) | decide what members can do, require sign-offs, classify repositories |
| [Teams and access](teams-and-access.md)                                | grant access to repositories through teams                            |

### Repositories

| Guide                                                       | Read it when you want to ...                                                       |
|-------------------------------------------------------------|------------------------------------------------------------------------------------|
| [Pull requests and merging](pull-requests.md)               | choose the merge methods, enable auto-merge or a merge queue                       |
| [Repository features and metadata](repository-features.md)  | enable issues, discussions or a wiki, and describe repositories                    |
| [Common repository patterns](repository-patterns.md)        | configure websites, mirrors, templates, forks or archived repositories             |

### When something goes wrong

| Guide                                    | Read it when you want to ...                                                             |
|------------------------------------------|------------------------------------------------------------------------------------------|
| [Troubleshooting](troubleshooting.md)    | understand a message of `validate` or an unexpected result of `plan` and `apply`          |

Administrators who maintain the default configuration for several organizations will find related information in
[Organization-wide policies](../../operating_otterdog/organization-policies.md).
