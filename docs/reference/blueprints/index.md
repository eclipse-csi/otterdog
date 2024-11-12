# Blueprints

Blueprints are a mechanism to help project to ensure that certain settings / files are present. They can be defined on global
or organization level. Any configured blueprint is also displayed in the dashboard.

Blueprints are defined in an *additive* manner (contrary to policies), i.e. multiple blueprints of the same type might be active for a single organization.
To distinguish blueprints of the same `type`, an additional `id` setting must be defined. If multiple blueprints use the same `id` value, only the first
encountered blueprint will be taken into account.

If a blueprint is defined for an organization, `otterdog` will check if the matching repositories of the organization
comply to the configuration of that blueprint. If this is not the case, a PR will be created to remediate the situation, e.g. by adding a file or updating
its contents. The committers of an organization still need to manually merge the PR but are able to edit it prior to merging.

If such a remediation PR gets closed without being merged, the associated blueprint for that repository is put into state `DISMISSED`,
and not further checks will be performed for that pair of blueprint / repository. In order to reinstate the checks, the PR needs to be reopened.

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
