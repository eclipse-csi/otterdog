Not all features or settings of a GitHub organization and its associated resources can be managed
by the means of `otterdog`. The following non-exhaustive list outlines settings that are currently not supported:

- setting the profile picture of an organization or a social media preview for a repository [#119](https://github.com/eclipse-csi/otterdog/issues/119)
- manage items that should be visible on the main page, i.e. releases, packages, deployments
- manage default repository labels on organization level
- secrets and variables for codespaces and dependabot
- managing GitHub apps or oauth policies
- managing pinned repositories for an organization
- supporting merge queue settings for a branch protection rule [#86](https://github.com/eclipse-csi/otterdog/issues/86)
- transfer a repo from one organization to another organization
- (deprecated) ~~tag protections~~ [#143](https://github.com/eclipse-csi/otterdog/issues/143), use rulesets instead

Most of the unsupported settings are only accessible via the Web UI of GitHub.
In case you would like to have a specific feature of GitHub being supported by `otterdog`,
please open a [ticket](https://github.com/eclipse-csi/otterdog/issues/new?template=Blank+issue).
