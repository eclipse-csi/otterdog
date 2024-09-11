Definition of an `Environment` on repository level, the following properties are supported:

| Key                        | Value                                   | Description                                                                           | Notes                                                              |
|----------------------------|-----------------------------------------|---------------------------------------------------------------------------------------|--------------------------------------------------------------------|
| _name_                     | string                                  | The name of the environment                                                           |                                                                    |
| _wait_timer_               | int                                     | The amount of time to wait before allowing deployments to proceed                     |                                                                    |
| _reviewers_                | list\[[Actor](actor.md)\]               | Users or Teams that may approve workflow runs that access this environment            |                                                                    |
| _deployment_branch_policy_ | string                                  | Limit which branches can deploy to this environment based on rules or naming patterns | `all`, `protected` or `selected`                                   |
| _branch_policies_          | list\[[BranchOrTag](branch-or-tag.md)\] | List of branch or tag patterns which can deploy to this environment                   | only applicable if `deployment_branch_policy` is set to `selected` |

## Jsonnet Function

``` jsonnet
orgs.newEnvironment('<name>') {
  <key>: <value>
}
```

## Validation rules

- specifying a non-empty list of `branch_policies` while `deployment_branch_policy` is not set to `selected` triggers a warning

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
