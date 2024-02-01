[`Otterdog`](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/) is a tool to manage GitHub organizations at
scale using an infrastructure as code approach. It is actively developed by the
[Eclipse Foundation](https://www.eclipse.org/) and used to manage its numerous projects hosted on
[GitHub](https://eclipsefdn.github.io/otterdog-configs/).

The infrastructure configuration for enabled GitHub organizations is hosted in a separate repository of the
organization itself and contributors can suggest changes to the configuration via pull requests. Changes to the
configuration need to be approved by the configured teams and applied manually using the `otterdog` command line tool.
