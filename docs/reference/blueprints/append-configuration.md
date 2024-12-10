# Append Configuration

This blueprint type will append a configuration snippet to the configuration of an organization
depending on a condition that is evaluated against the current configuration.

## Configuration

- `type` - `append_configuration`

### Settings

| Setting   | Necessity | Value type   | Description                                                                        |
|-----------|-----------|--------------|------------------------------------------------------------------------------------|
| condition | mandatory | string       | a [JSONata](https://jsonata.org/) expression that is evaluated against the current configuration |
| content   | mandatory | string       | the configuration snippet to add if the `condition` evaluates to `true`            |
| reviewers | optional  | list[string] | the list of teams for which a review shall be requested upon pull request creation |

!!! note

    Team names will be implicitly slugified, i.e. a team name defined with a template like `technology.csi-project-leads`
    will be converted to `technology-csi-project-leads`.

### Templating

It is possible to use [Mustache](https://mustache.github.io/) logic-less templates within the `content` / `reviewers` parameters of this blueprint.

To use a context variable, simply enclose its name in curly braces:

```yaml
  This is an example to use mustache template for repo: {{repo_name}}
```

In this example, `{{repo_name}}` will be replaced with the actual name of the repository being processed. For more complex examples please refer
to the [mustache documentation](https://mustache.github.io/mustache.5.html).


#### Template Context

The following context is injected during template evaluation when a specific repository is being processed:

| Variable      | Type   | Description                                                                                                                   |
|---------------|--------|-------------------------------------------------------------------------------------------------------------------------------|
| project_name  | string | the project name of the associated GitHub organization, e.g. `technology.csi`                                                 |
| github_id     | string | the name of the associated GitHub organization                                                                                |
| repo_name     | string | the name of the repository being processed                                                                                    |
| org           | dict   | the [organization settings](../organization/settings.md) for the associated GitHub organization                               |
| repo          | dict   | the [repository settings](../organization/repository/index.md) for the repository being processed                             |
| repo_url      | string | the url of the repository being processed, e.g. `https://github.com/eclipse-csi/otterdog`                                     |
| blueprint_id  | string | the id of the associated blueprint, e.g. `require-dependabot-auto-merge`                                                      |
| blueprint_url | string | the url of the associated blueprint, e.g. `https://github.com/eclipse-csi/.eclipsefdn/blob/main/otterdog/blueprints/test.yml` |

### References

- [JSONata playground](https://try.jsonata.org/)
- [JSONata documentation](https://docs.jsonata.org/overview.html)

## Example

The following example adds an [Organization Ruleset](../organization/ruleset.md) to the configuration to prevent force-pushes
on the default branch of any repository if one does not exist yet:

``` yaml
id: prevent-force-pushes
name: Prevents force-pushes for the default branch
type: append_configuration
config:
  condition: >-
    $count($.rulesets[allows_force_pushes = false and
    "~DEFAULT_BRANCH" in include_refs and
    "~ALL" in include_repo_names and target = "branch"]) = 0
  content: |-
    {
      # snippet added due to '{{blueprint_url}}'
      rulesets+: [
        orgs.newOrgRuleset('{{blueprint_id}}') {
          allows_creations: true,
          include_repo_names: [
            "~ALL"
          ],
          include_refs: [
            "~DEFAULT_BRANCH"
          ],
          required_pull_request: null,
          required_status_checks: null,
        },
      ],
    }
```
