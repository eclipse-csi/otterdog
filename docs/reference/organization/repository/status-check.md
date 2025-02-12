A [Branch Protection Rule](branch-protection-rule.md) or [Ruleset](ruleset.md) allows to reference certain
status checks that are required to pass before a pull request can be merged into the target branch.

| Source   | Format                     | Example                                 |
|----------|----------------------------|-----------------------------------------|
| Workflow | `<job-name>`               | `Run CI`                                |
| App      | `<app-slug>:<status-name>` | `eclipse-eca-validation:eclipsefdn/eca` |
| Any      | `any:<status-name>`        | `any:Run CI`                            |

!!! note

    [Rulesets](ruleset.md) do not make any distinction between `Any` or `Workflow` as source and thus
    specifying `any:` is not needed for them and will give the same result as omitting it.

## Workflows as Required Status Checks

Given the following workflows `ci.yaml` and `job-legal.yaml` in a GitHub repository:

=== "ci.yaml"

    ```yaml
    name: ci

    on:
      pull_request:
        ...

    jobs:
      build:
        ...

      test:
        name: testing
        ...

      call-legal:
        uses: ./.github/workflows/job-legal.yaml
    ```

=== "job-legal.yaml"

    ```yaml
    name: legal
    on:
      workflow_call:  # allow this workflow to be called from other workflows
        ...

    jobs:
      legal:
        name: Legal Checks
        ...
    ```

Based on these workflow files, the following status checks would be available:

- `build`: references the job build in the ci workflow by its id as it has no name specified
- `testing`: references the job test in the ci workflow by its name testing
- `call-legal / Legal Checks`: references the job legal by its name `Legal Checks` in the workflow job-legal.yaml that is called from the job legal in the ci workflow

Rules for translating jobs to stats-checks:

- if a job has no name specified, use its id
- if reusable workflows are called, join the jobs in their call hierarchy with ` / `

!!! note

    Be aware of the mandatory whitespaces surrounding the `/`. In case they are omitted, the status check will not
    be correctly recognized by GitHub. Please refer also the example outlined above.

Now, as an example to protect the `main` branch by enforcing specific status checks to pass before a pull request can be merged into it,
you can add the status checks as below:

```jsonnet
orgs.newBranchProtectionRule('main') {
    required_status_checks+: [
        "build",
        "call-legal / Legal Checks"
    ]
}
```
