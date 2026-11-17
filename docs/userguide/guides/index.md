# Configuration Guides

The guides start from a need, e.g. protecting a release branch or limiting the permissions of workflows, and explain
how to address it with otterdog: which properties to use, what the consequences of each choice are and which
trade-offs to consider. They complement the [Reference](../../reference/index.md), which documents every supported
property. To add, rename or remove a resource, see [Adding, renaming and removing resources](../resources.md),
and when something goes wrong, see [Troubleshooting](troubleshooting.md).

<!-- the order of the guides below is the one of the examples in the Playground, see docs_playground.py -->

## Fundamentals

<div class="grid cards" markdown>

-   :material-family-tree:{ .lg .middle } **[Inherited and explicit values](inheritance.md)**

    ---

    Understand where a value comes from, and why a `plan` shows a change.

-   :material-recycle:{ .lg .middle } **[Reusing configuration with Jsonnet](reusable-configuration.md)**

    ---

    Share settings between many repositories without copying them.

</div>

## Protecting code

<div class="grid cards" markdown>

-   :material-source-branch-check:{ .lg .middle } **[Protecting branches](branch-protection.md)**

    ---

    Protect the default branch or the release branches.

-   :material-domain:{ .lg .middle } **[Organization-wide rulesets](organization-rulesets.md)**

    ---

    Apply the same protection to many repositories.

-   :material-scale-balance:{ .lg .middle } **[Rulesets or branch protection rules](rulesets-vs-branch-protection.md)**

    ---

    Choose between the two mechanisms.

-   :material-swap-horizontal:{ .lg .middle } **[Migrating to rulesets](migrating-to-rulesets.md)**

    ---

    Replace branch protection rules with rulesets without losing protection.

-   :material-tag-outline:{ .lg .middle } **[Protecting tags and releases](tag-protection.md)**

    ---

    Prevent release tags from being moved or deleted.

</div>

## Security and automation

<div class="grid cards" markdown>

-   :material-cog-play-outline:{ .lg .middle } **[Securing GitHub Actions](github-actions.md)**

    ---

    Limit the permissions of workflows, control which actions can run, and who and what can run the workflows.

-   :material-shield-lock-outline:{ .lg .middle } **[Repository security features](repository-security.md)**

    ---

    Enable secret scanning, Dependabot, code scanning and vulnerability reporting, or apply code security
    configurations.

-   :material-key-variant:{ .lg .middle } **[Secrets and variables](secrets-and-variables.md)**

    ---

    Provide credentials to workflows without exposing them.

-   :material-cloud-upload-outline:{ .lg .middle } **[Deployment environments](environments.md)**

    ---

    Protect deployments and publishing with approvals and branch restrictions.

-   :material-webhook:{ .lg .middle } **[Webhooks](webhooks.md)**

    ---

    Connect external services securely.

</div>

## Organization and access

<div class="grid cards" markdown>

-   :material-office-building-cog-outline:{ .lg .middle } **[Organization settings and member privileges](organization-settings.md)**

    ---

    Decide what members can do, require sign-offs, classify repositories.

-   :material-account-group-outline:{ .lg .middle } **[Teams and access](teams-and-access.md)**

    ---

    Grant access to repositories through teams.

</div>

## Repositories

<div class="grid cards" markdown>

-   :material-source-pull:{ .lg .middle } **[Pull requests and merging](pull-requests.md)**

    ---

    Choose the merge methods, enable auto-merge or a merge queue.

-   :material-tag-text-outline:{ .lg .middle } **[Repository features and metadata](repository-features.md)**

    ---

    Enable issues, discussions or a wiki, and describe repositories.

-   :material-shape-outline:{ .lg .middle } **[Common repository patterns](repository-patterns.md)**

    ---

    Configure websites, mirrors, templates, forks or archived repositories.

</div>

## How to read the guides

<!-- the Playground, where every example can be tried out, drawn by docs/assets/theme.css -->
<div class="otterdog-hero" markdown>

:material-code-braces:{ .otterdog-hero__icon }

<div class="otterdog-hero__body" markdown>

**Try every example in the Playground**

The link below an example opens it in the Playground of the otterdog dashboard, which also lists all the examples of
these guides: change it, see the resulting configuration and check it, without installing anything.

[:material-open-in-new: Open the Playground](https://otterdog.eclipse.org/playground){ .md-button .md-button--primary }

</div>

</div>

<div class="grid cards" markdown>

-   :material-text-box-check-outline:{ .lg .middle } **Complete and minimal examples**

    ---

    Each example is a complete organization configuration that only contains the properties relevant to the topic,
    all the others are inherited from the default configuration. The `import` statement at the top of the
    configuration file is omitted.

-   :material-file-cog-outline:{ .lg .middle } **The example default configuration**

    ---

    The values that an example inherits come from the
    [example default configuration](https://github.com/eclipse-csi/otterdog/blob/main/otterdog/resources/defaults/otterdog-defaults.libsonnet).
    The default configuration of your organization may define other values. The Playground can evaluate an example
    with either of them.

-   :material-credit-card-outline:{ .lg .middle } **GitHub plans matter**

    ---

    Some features of GitHub are only available for some plans or repository visibilities, otterdog cannot enable
    what GitHub does not provide. The guides mention the availability and link to the GitHub documentation, which
    remains the authoritative source.

-   :material-map-legend:{ .lg .middle } **Recommendations and policies**

    ---

    The guides tell general recommendations apart from the choices that depend on the policy of your organization,
    see below.

</div>

!!! tip "Recommendation"

    A practice that is recommended in general, usually based on the GitHub documentation.

!!! info "Organization policy"

    A choice that depends on the requirements, the size or the governance of your organization.

Administrators who maintain the default configuration for several organizations will find related information in
[Organization-wide policies](../../operating_otterdog/organization-policies.md).
