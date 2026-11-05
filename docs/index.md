# otterdog

Otterdog manages GitHub organizations at scale with a configuration as code approach: the settings of an
organization and of its repositories are declared in [Jsonnet](https://jsonnet.org/), reviewed as pull requests and
applied to GitHub. It is developed by the [Eclipse Foundation](https://www.eclipse.org/), which uses it to manage
[the GitHub organizations of its projects](https://eclipsefdn.github.io/otterdog-configs/).

## How it works

<!-- the steps of a change, drawn by docs/assets/theme.css -->
<div class="otterdog-flow" markdown>

<div class="otterdog-flow__step" markdown>

:material-file-code-outline:{ .otterdog-flow__icon }

**Declare**

A repository of the organization declares its settings, teams and repositories in Jsonnet.

</div>

<div class="otterdog-flow__step" markdown>

:material-source-pull:{ .otterdog-flow__icon }

**Propose**

Anyone proposes a change as a pull request, tried out in the Playground if needed.

</div>

<div class="otterdog-flow__step" markdown>

:material-shield-check-outline:{ .otterdog-flow__icon }

**Review**

otterdog validates it and shows what it would change on GitHub, the configured teams approve.

</div>

<div class="otterdog-flow__step" markdown>

:material-rocket-launch-outline:{ .otterdog-flow__icon }

**Apply**

Once the pull request is merged, otterdog applies the changes to the GitHub organization.

</div>

</div>

The configuration only declares what differs from a [default configuration](userguide/guides/inheritance.md) shared
by many organizations, and administrators can also apply changes with the `otterdog` command line tool. See
[Workflow for changes](userguide/workflow.md) for the steps of a change.

## What otterdog manages

- **Organizations**: [settings](reference/organization/settings.md), [roles](reference/organization/role.md),
  [teams](reference/organization/team.md), [webhooks](reference/organization/webhook.md),
  [secrets](reference/organization/secret.md) and [variables](reference/organization/variable.md),
  [rulesets](reference/organization/ruleset.md), [custom properties](reference/organization/custom-property.md) and
  [code security configurations](reference/organization/code-security-configuration.md).
- **Repositories**: [settings](reference/organization/repository/index.md),
  [branch protection rules](reference/organization/repository/branch-protection-rule.md) and
  [rulesets](reference/organization/repository/ruleset.md),
  [environments](reference/organization/repository/environment/index.md),
  [webhooks](reference/organization/repository/webhook.md), [secrets](reference/organization/repository/secret.md)
  and [variables](reference/organization/repository/variable.md).
- **Across organizations**: [policies](reference/policies/index.md) enforce a behavior, and
  [blueprints](reference/blueprints/index.md) keep files and settings present in repositories by opening pull
  requests.

Some settings are only available in the web interface of GitHub, otterdog manages them through a browser session.
Others cannot be managed at all, see [Unsupported settings](userguide/unsupported.md).

## Where to go next

<div class="grid cards" markdown>

-   :material-source-pull:{ .lg .middle } **Getting started**

    ---

    Find the path that matches your role: change the configuration of an organization, manage organizations with
    the command line tool or deploy otterdog.

    [:material-arrow-right: Getting started](getting-started.md)

-   :material-book-open-variant:{ .lg .middle } **User Guide**

    ---

    Make a change, then follow the configuration guides: protect branches and tags, secure GitHub Actions, manage
    secrets, teams and repositories.

    [:material-arrow-right: User Guide](userguide/index.md)

-   :material-file-tree-outline:{ .lg .middle } **Reference**

    ---

    Every resource and property of a configuration, the policies, the blueprints and the operations of the command
    line tool.

    [:material-arrow-right: Reference](reference/index.md)

-   :material-view-dashboard-outline:{ .lg .middle } **Dashboard and Playground**

    ---

    Browse the organizations managed by otterdog at the Eclipse Foundation and their configuration. Its Playground
    evaluates a configuration in your browser and checks its values like otterdog does, before you open a pull
    request: every complete example of the guides opens in it.

    [:material-arrow-right: Open the dashboard](https://otterdog.eclipse.org)<br>
    [:material-arrow-right: Open the Playground](https://otterdog.eclipse.org/playground)

-   :material-server-outline:{ .lg .middle } **Operating otterdog**

    ---

    Install the command line tool or deploy the GitHub App, set up credentials and the default configuration of
    your organizations.

    [:material-arrow-right: Operating otterdog](operating_otterdog/index.md)

-   :material-code-braces:{ .lg .middle } **Developing otterdog**

    ---

    Set up a development environment, understand the architecture and contribute to otterdog.

    [:material-arrow-right: Developing otterdog](developing_otterdog/index.md)

</div>
