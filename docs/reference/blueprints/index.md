# Blueprints

Blueprints are a mechanism to help project to ensure that certain settings / files are present. They can be defined on global
or organization level. Any configured blueprint is also displayed in the dashboard.

Blueprints are defined in an *additive* manner (contrary to policies), i.e. multiple blueprints of the same type might be active for a single organization.
To distinguish blueprints of the same `type`, an additional `id` setting must be defined. If multiple blueprints use the same `id` value, only the first
encountered blueprint will be taken into account.

If a blueprint is defined for an organization, `otterdog` will check if the matching repositories of the organization
comply to the configuration of that blueprint. If this is not the case, a PR will be created to remediate the situation, e.g. by adding a file or updating
its contents. The committers of an organization still need to manually merge the PR but are able to edit it prior to merging.

If such a remediation PR gets closed without being merged, or `/otterdog ignore` is commented on it, the associated blueprint for that
repository is put into state `DISMISSED`, and no further checks will be performed for that pair of blueprint / repository. In order to
reinstate the checks, comment `/otterdog recreate` on the PR, or reopen it. Before remediating, `otterdog` also checks the latest PR of
the blueprint branch (`otterdog/blueprint/<id>`) on GitHub: if it was closed without being merged and the stored status still refers to
it (or got lost), the blueprint is put into state `DISMISSED` again, so a dismissed remediation PR is never recreated by accident.

## Remediation branches

Remediation pull requests use the branch `otterdog/blueprint/<id>`. Before writing content, otterdog brings an
existing branch up to date with the default branch:

- a branch whose commits were all made by otterdog (its bot user, not other bots) is reset onto the head of the
  default branch and its files are written again, so stale commits disappear
- a branch carrying commits of maintainers gets the default branch merged in, so their edits are preserved; a
  conflicting merge is left untouched and logged

A push to the default branch of a repository with an open remediation pull request triggers this update, so the pull
request stays mergeable. `/otterdog rebase` and `/otterdog recreate` trigger it on demand, see
[comment commands](commands.md).

## Check frequency

Blueprints are evaluated when `/internal/check` is called, every 5 minutes by default (`policies.schedule` in the Helm chart).
A blueprint is evaluated at most once per `BLUEPRINT_CHECK_INTERVAL` seconds for a given organization, one hour by default
(`config.blueprintCheckInterval` in the Helm chart). Calls within that interval skip the blueprint, which is logged at debug level:

```
skipping blueprint with id '<id>' for org '<org>', last checked at '<date>'
```

A change to a blueprint definition is therefore picked up at the next evaluation, at most `BLUEPRINT_CHECK_INTERVAL` seconds later.

## Configuration

Blueprints are defined using a `yaml` syntax and placed in the `otterdog/blueprints` folder of
the config repository using either a `.yml` or `.yaml` extension.

### Example

``` yaml
id: default-security-policy
name: Adds a default SECURITY.md file
description: |-
  This blueprint will create a PR that will add a default SECURITY.md file to the `.github` repo of your GitHub organization if it does not yet exist.
  You can adjust the PR as needed to fit it to your needs. If a repo defines a more specific SECURITY.md file it will take precedence of the one present in the `.github` repo.
type: required_file
config:
  repo_selector:
    name_pattern: .github
  files:
    - path: SECURITY.md
      content: |
        # Security Policy
        This Eclipse Foundation Project adheres to the [Eclipse Foundation Vulnerability Reporting Policy](https://www.eclipse.org/security/policy/).
        ...
```

### Settings

| Setting     | Necessity | Description                                                |
|-------------|-----------|------------------------------------------------------------|
| id          | mandatory | unique identification of the blueprint                     |
| name        | optional  | Name of the blueprint as displayed in the dashboard        |
| description | optional  | Description of the blueprint as displayed in the dashboard |
| type        | mandatory | Type of the blueprint                                      |
| config      | mandatory | Custom configuration dependent on the `type` of blueprint  |

Every `config` additionally accepts the following settings that control the remediation pull request:

| Setting   | Necessity | Value type   | Description                                                                                   |
|-----------|-----------|--------------|-----------------------------------------------------------------------------------------------|
| labels    | optional  | list[string] | labels added to the PR, in addition to `otterdog` and `blueprint:<id>` which are always added |
| reviewers | optional  | list[string] | team slugs requested as reviewers                                                             |
| assignees | optional  | list[string] | users assigned to the PR                                                                      |
| status_workflow | optional | string \| list[string] | workflow(s) whose jobs `/otterdog status` reports, by file name or workflow name; defaults to the workflows the blueprint manages, or all |

## Remediation pull requests

A remediation pull request carries the labels `otterdog` and `blueprint:<id>` (adding labels needs the GitHub App
permission `Issues: Read & Write`). Its body lists the blueprint, the files it touches, whether each file was written
from the blueprint or kept as edited on the branch, the blueprint *revision* the content was rendered from, and the
comment commands available on the pull request, see [comment commands](commands.md).

The revision is a digest of the blueprint's configuration. It is stored with the remediation when all files were
written, so `/otterdog status` can flag pull requests whose content is older than the current blueprint. Non-strict
files are written again on every evaluation as long as the branch only carries otterdog commits; once a maintainer
has pushed to the branch they are kept as edited.
