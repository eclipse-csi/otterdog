Definition of an Environment on repository level, the following properties are supported:

| Key                      | Value        | Description                                                                                                                      |
|--------------------------|--------------|----------------------------------------------------------------------------------------------------------------------------------|
| name                     | string       | The name of the environment                                                                                                      |
| wait_timer               | int          | The amount of time to wait before allowing deployments to proceed                                                                |
| reviewers                | list[actor]  | Users or Teams that may approve workflow runs that access this environment                                                       |
| deployment_branch_policy | string       | Limit which branches can deploy to this environment based on rules or naming patterns, can be `all` or `protected` or `selected` |
| branch_policies          | list[string] | List of branch patterns which can deploy to this environment, only used when `deployment_branch_policy` is set to `selected`     |

## Jsonnet Function

``` jsonnet
orgs.newEnvironment('<name>') {
  <key>: <value>
}
```

## Validation rules

- redacted secret values (`********`) trigger a validation info and will skip the secret during processing

## Example usage

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('OtterdogTest') {
      ...
      _repositories+:: [
        ...
        orgs.newRepo('test-repo') {
          ...
          environments: [
            orgs.newEnvironment('linux') {
              deployment_branch_policy: "protected",
              reviewers+: [
                "@OtterdogTest/eclipsefdn-security",
                "@netomi"
              ],
              wait_timer: 30,
            },
          ]
        }
      ]
    }
    ```
