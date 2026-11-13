Definition of a `Repository Actions Policy`, the following properties are supported:

| Key                  | Value                                            | Description                                                  | Notes                                                                                        |
|----------------------|--------------------------------------------------|--------------------------------------------------------------|----------------------------------------------------------------------------------------------|
| _name_               | string                                           | The name of this actions policy                              | Must be unique within the repository                                                         |
| _enforcement_        | string                                           | The enforcement status of this actions policy                | `active`, `disabled` or `evaluate`, `evaluate` is only available with GitHub Enterprise      |
| _include_workflows_  | list\[string\]                                   | List of workflow files or patterns targeted by the policy    | `~ALL` targets all workflows, e.g. `.github/workflows/release.yml` or `.github/workflows/*` |
| _exclude_workflows_  | list\[string\]                                   | List of workflow files or patterns excluded from the policy  | `~ALL` is not allowed                                                                        |
| _allowed_actors_     | list\[[AllowedActor](allowed-actor.md)\] or null | Rule: the actors allowed to run the targeted workflows       | `null` does not require the rule                                                             |
| _allowed_events_     | list\[string\] or null                           | Rule: the events allowed to trigger the targeted workflows   | e.g. `push`, `pull_request` or `workflow_dispatch`, `null` does not require the rule         |

An actions policy, called workflow execution protection by GitHub, blocks the runs of the targeted workflows that
it does not allow, see
[Controlling workflow execution](https://docs.github.com/en/actions/how-tos/administer/control-workflow-execution).

Like rulesets, actions policies layer with the policies of the organization and the enterprise: a run must be
allowed by all the policies that target its workflow. The policies of the organization are defined with the
[Organization Actions Policy](../actions-policy.md).

A workflow pattern matches the path of a workflow file in the repository, an empty `include_workflows` targets all
the workflows that `exclude_workflows` does not exclude.

The rules of a policy that otterdog does not support, e.g. **Require lockfile** whose rule GitHub does not
publish in its API yet, are kept when otterdog updates the policy. A rule missing from the configuration, e.g. with
a default configuration predating it, is not managed either and keeps its current value.

## Jsonnet Function

``` jsonnet
orgs.newRepoActionsPolicy('<name>') {
  <key>: <value>
}
```

The default values of an actions policy:

``` jsonnet
--8<-- "otterdog/resources/defaults/otterdog-defaults.libsonnet:actions_policy"
```

## Validation rules

- setting `enforcement` to `evaluate` for an organization on a non `enterprise` plan triggers an error
- setting both `include_workflows` and `exclude_workflows` to empty lists triggers an error, use `~ALL` to target all workflows
- combining `~ALL` with other patterns in `include_workflows`, or using `~ALL` in `exclude_workflows` triggers an error
- setting an invalid allowed actor, e.g. an unknown role, triggers an error
- setting an event in `allowed_events` that otterdog does not know triggers a warning
- setting `allowed_actors` or `allowed_events` to an empty list triggers a warning, as it blocks all the targeted workflows
- a policy that does not require any rule triggers a warning, as it has no effect

## Example usage

The following policy only allows the maintainers of the repository and the `releng` team to run its release
workflow:

=== "jsonnet"
    ``` jsonnet
    orgs.newOrg('my-project', 'my-org') {
      _repositories+:: [
        orgs.newRepo('my-repo') {
          actions_policies: [
            orgs.newRepoActionsPolicy('release') {
              include_workflows: [
                ".github/workflows/release.yml"
              ],
              allowed_actors: [
                "#Maintain",
                "@my-org/releng"
              ],
            },
          ],
        },
      ],
    }
    ```
