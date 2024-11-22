# Append Configuration

This blueprint type will append a configuration snippet to the configuration of an organization
depending on a condition that is evaluated against the current configuration.

## Configuration

- `type` - `append_configuration`

### Settings

| Setting   | Necessity | Value type | Description                                                                                      |
|-----------|-----------|------------|--------------------------------------------------------------------------------------------------|
| condition | mandatory | string     | a [JSONata](https://jsonata.org/) expression that is evaluated against the current configuration |
| content   | mandatory | string     | the configuration snippet to add if the `condition` evaluates to `true`                          |

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
