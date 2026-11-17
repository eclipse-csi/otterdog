# User Guide

This guide is for the developers who change the GitHub organizations and repositories of their project through an
existing otterdog setup: the day-to-day path from a need to a change applied on GitHub. To install and operate
otterdog itself, see [Operating Otterdog](../operating_otterdog/index.md).

<!-- the path through the user guide, drawn by docs/assets/theme.css -->
<div class="otterdog-flow" markdown>

<div class="otterdog-flow__step" markdown>

:material-map-marker-path:{ .otterdog-flow__icon }

**Learn the workflow**

How a change goes from a pull request to GitHub, see [Workflow for changes](workflow.md).

</div>

<div class="otterdog-flow__step" markdown>

:material-compass-outline:{ .otterdog-flow__icon }

**Find your guide**

Start from your need in the [Configuration Guides](guides/index.md).

</div>

<div class="otterdog-flow__step" markdown>

:material-code-braces:{ .otterdog-flow__icon }

**Try it**

Edit and check your change in the Playground of the [dashboard](https://otterdog.eclipse.org).

</div>

<div class="otterdog-flow__step" markdown>

:material-source-pull:{ .otterdog-flow__icon .otterdog-flow__icon--done }

**Propose it**

Open the pull request, otterdog validates and applies it.

</div>

</div>

## Making changes

Every change to the configuration of an organization is a pull request on its configuration repository.

<div class="grid cards" markdown>

-   :material-map-marker-path:{ .lg .middle } **[Workflow for changes](workflow.md)**

    ---

    From the Playground or a branch to the changes applied on GitHub: the validation, the review, the auto-merge
    with `/otterdog merge` and the apply.

-   :material-file-document-edit-outline:{ .lg .middle } **[Adding, renaming and removing resources](resources.md)**

    ---

    Declare a new resource with the function of the default configuration, rename a repository or a webhook without
    deleting it, delete a resource.

</div>

## Configuration Guides

The [Configuration Guides](guides/index.md) start from common needs and explain how to address them with otterdog,
including the trade-offs and limitations to consider. Every property is documented in the
[Reference](../reference/index.md).

<div class="grid cards" markdown>

-   :material-family-tree:{ .lg .middle } **Fundamentals**

    ---

    [Inherited and explicit values](guides/inheritance.md) ·
    [Reusing configuration with Jsonnet](guides/reusable-configuration.md)

-   :material-source-branch-check:{ .lg .middle } **Protecting code**

    ---

    [Protecting branches](guides/branch-protection.md) ·
    [Organization-wide rulesets](guides/organization-rulesets.md) ·
    [Rulesets or branch protection rules](guides/rulesets-vs-branch-protection.md) ·
    [Migrating to rulesets](guides/migrating-to-rulesets.md) ·
    [Protecting tags and releases](guides/tag-protection.md)

-   :material-shield-lock-outline:{ .lg .middle } **Security and automation**

    ---

    [Securing GitHub Actions](guides/github-actions.md) ·
    [Repository security features](guides/repository-security.md) ·
    [Secrets and variables](guides/secrets-and-variables.md) ·
    [Deployment environments](guides/environments.md) ·
    [Webhooks](guides/webhooks.md)

-   :material-account-group-outline:{ .lg .middle } **Organization and access**

    ---

    [Organization settings and member privileges](guides/organization-settings.md) ·
    [Teams and access](guides/teams-and-access.md)

-   :material-source-repository-multiple:{ .lg .middle } **Repositories**

    ---

    [Pull requests and merging](guides/pull-requests.md) ·
    [Repository features and metadata](guides/repository-features.md) ·
    [Common repository patterns](guides/repository-patterns.md)

</div>

!!! tip "New to otterdog?"

    Start with the fundamentals: [Inherited and explicit values](guides/inheritance.md) explains where the values of
    a configuration come from, and why a `plan` may show changes nobody made.

## When something goes wrong

<div class="grid cards" markdown>

-   :material-stethoscope:{ .lg .middle } **[Troubleshooting](guides/troubleshooting.md)**

    ---

    Understand a message of the validation, a reply of `/otterdog merge`, or an unexpected result of `plan` and
    `apply`.

-   :material-cancel:{ .lg .middle } **[Unsupported settings](unsupported.md)**

    ---

    The features and settings of GitHub that otterdog does not manage, and how to change them.

</div>
