# User Guide

**This guide is aimed at developers who use otterdog to manage GitHub organizations and repositories via an existing otterdog setup.**

It focuses on the day-to-day workflow for making changes through configuration and pull requests, not on operating
otterdog itself, see [Operating Otterdog](../operating_otterdog/index.md) for that.

## Making changes

Every change to the configuration of an organization is a pull request on its configuration repository:

- [Workflow for changes](workflow.md): from the configuration repository to the changes applied on GitHub.
- [Adding resources](adding.md): declare a new resource, e.g. a repository, with the function of the default
  configuration.
- [Renaming resources](renaming.md): rename a resource without deleting and recreating it.
- [Removing resources](removal.md): delete a resource from the configuration.

## Configuration Guides

The [Configuration Guides](guides/index.md) start from common needs, e.g. protecting branches and tags, securing
GitHub Actions or managing secrets, and explain how to address them with otterdog, including the trade-offs and
limitations to consider. Start with the fundamentals: [Inherited and explicit values](guides/inheritance.md) and
[Reusing configuration with Jsonnet](guides/reusable-configuration.md).

## Troubleshooting & limits

- [Troubleshooting](guides/troubleshooting.md): understand a message of `validate` or an unexpected result of `plan`
  and `apply`.
- [Unsupported settings](unsupported.md): the features and settings of GitHub that otterdog cannot manage.
