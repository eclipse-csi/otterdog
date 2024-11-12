# Policies

Policies are a mechanism to enforce certain behavior within a project / organization. They can be defined on global
or organization level. Any configured policy is also displayed in the dashboard.

If a policy is defined for an organization, its configured behavior can not be dismissed or ignored by the organization,
unless the configuration is overwritten on organization level, i.e. on global level the use of `macOS large runners` is
disabled, but it can be enabled per organization if it is eligible. In order to override the settings of policy, the same
`type` must be used, as a consequence, there can only be one policy of a certain type be active for a single organization.

## Configuration

Policies are defined using a `yaml` syntax and placed in the `otterdog/policies` folder of
the config repository using either a `.yml` or `.yaml` extension.

### Example

``` yaml
name: a meaningful name of the policy
description: |-
  This is the description that will be displayed in the dashboard,
  and will also be included in any PR that will be opened if needed.
type: <policy-type>
config:
  ... # policy specific configuration
```

### Settings

| Setting     | Necessity | Description                                             |
|-------------|-----------|---------------------------------------------------------|
| name        | optional  | Name of the policy as displayed in the dashboard        |
| description | optional  | Description of the policy as displayed in the dashboard |
| type        | mandatory | Type of the policy                                      |
| config      | mandatory | Custom configuration dependent on the `type` of policy  |
