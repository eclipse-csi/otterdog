# Getting started

How you start with otterdog depends on what you want to do. Most people only change the configuration of an
organization through pull requests and never install anything.

## Change the configuration of an organization

For the members and contributors of a project whose GitHub organization is managed by otterdog.

1. **Find the configuration repository** of the organization, e.g. `.eclipsefdn` for the projects of the Eclipse
   Foundation. The configuration of the organization is `otterdog/<organization>.jsonnet`.
2. **Find what to change**: the [Configuration Guides](userguide/guides/index.md) start from a need, e.g.
   protecting a branch or providing a secret to a workflow, the [Reference](reference/index.md) documents every
   property. The configuration only declares what differs from the default configuration, see
   [Inherited and explicit values](userguide/guides/inheritance.md).
3. **Try it out** (optional): the [Playground](https://otterdog.eclipse.org/playground) evaluates a configuration
   and checks its values like otterdog does.
4. **Open a pull request** on the configuration repository: otterdog validates it and shows the changes it would
   make on GitHub, the configured teams review it, and the changes are applied once it is merged.

Next: [Workflow for changes](userguide/workflow.md), then
[adding](userguide/adding.md), [renaming](userguide/renaming.md) or [removing](userguide/removal.md) resources.

## Manage organizations with the command line tool

For the administrators of GitHub organizations, who apply configurations themselves.

1. **Install** git and otterdog, see [Install](operating_otterdog/install.md):

    ```shell
    pipx install otterdog
    ```

2. **Configure** the organizations to manage in an `otterdog.json` file: the default configuration to use and the
   credentials to access each organization (a GitHub token, and a GitHub account with two-factor authentication
   for the settings only available in the web interface), see [Setup](operating_otterdog/setup.md).
3. **Import** the current configuration of an organization, then review and apply changes:

    ```shell
    otterdog import <organization>   # writes the configuration of the organization from its live settings
    otterdog plan <organization>     # shows the changes that would be applied
    otterdog apply <organization>    # applies them
    ```

Next: [Usage of the command line tool](operating_otterdog/usage.md) and the [CLI Operations](reference/operations/index.md).

## Deploy otterdog for your organizations

For the operators who run the otterdog GitHub App, which validates the pull requests of configuration
repositories, applies the merged changes and provides the dashboard and its Playground.

1. **Create a GitHub App** and install it in the organizations to manage.
2. **Deploy** the container image with the Helm chart on Kubernetes, and initialize otterdog.
3. **Define the policies** shared by your organizations: the default configuration, validation scripts and
   exceptions, see [Organization-wide policies](operating_otterdog/organization-policies.md).

Next: [Otterdog WebApp](operating_otterdog/install.md#otterdog-webapp).

## Contribute to otterdog

For the developers of otterdog itself.

1. **Set up** a development environment with `make init`, see [Development Setup](developing_otterdog/development_setup.md).
2. **Read** the [Architecture](developing_otterdog/architecture.md) and the
   [Coding & Style Guidelines](developing_otterdog/coding_style.md).
3. **Propose** your change as described in the [Contribution Workflow](developing_otterdog/contribution_workflow.md).

Next: [Testing](developing_otterdog/testing.md) and the [Release Process](developing_otterdog/release_process.md).
