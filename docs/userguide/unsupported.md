Not all features or settings of a GitHub organization and its associated resources can be managed
by the means of `otterdog`. The following non-exhaustive list outlines settings that are currently not supported:

- setting the profile picture of an organization or a social media preview for a repository [#119](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/119)
- manage default repository labels on organization level
- manage custom properties
- organization rulesets (only rulesets on repo level are supported atm)
- secrets and variables for codespaces and dependabot
- managing GitHub apps or oauth policies
- managing pinned repositories for an organization
- enabling private vulnerability reporting [#27](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/27)
- tag protections [#143](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/143)
- supporting merge queue settings for a branch protection rule [#86](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/86)
- transfer a repo from one organization to another organization

Most of the unsupported settings are only accessible via the Web UI of GitHub.
In case you would like to have a specific feature of GitHub being supported by `otterdog`,
please open a ticket [at](https://gitlab.eclipse.org/eclipsefdn/security/otterdog/-/issues/new).
