# CLI Operations

The CLI has support for various operations to operate on individual organizations. In general, if no organization is specified,
the selected operation runs on all organizations defined in the used configuration file (_otterdog.json_).

```shell
Usage: otterdog [OPTIONS] COMMAND [ARGS]...

  Managing GitHub organizations at scale.

Options:
  --version   Show the version and exit.
  -h, --help  Show this message and exit.

Commands:
  apply           Apply changes based on the current configuration to the live configuration at GitHub.
  canonical-diff  Displays a diff of the current configuration to a canonical version.
  fetch-config    Fetches the configuration from the corresponding config repo of an organization.
  import          Imports existing resources for a GitHub organization.
  local-plan      Show changes to another local configuration.
  plan            Show changes to live configuration on GitHub.
  push-config     Pushes the local configuration to the corresponding config repo of an organization.
  show            Displays the full configuration for organizations.
  show-live       Displays the live configuration for organizations.
  sync-template   Sync contents of repositories created from a template repository.
  validate        Validates the configuration for organizations.
  web-login       Open a browser window logged in to the GitHub organization.
```

## Working directory

When running otterdog, all used data is stored and accessed locally. The configuration files for each
organization are expected to be at location `$CWD/<config-dir>/<github-id>/`, where `<config-dir>` can be configured
in `otterdog.json` and defaults to `orgs`.


