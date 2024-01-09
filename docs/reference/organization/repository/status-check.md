A [Branch Protection Rule](branch-protection-rule.md) allows to reference certain status checks
that are required to pass before a pull request can be merged into the target branch.

| Source   | Format                     | Example                                 |
|----------|----------------------------|-----------------------------------------|
| Workflow | `<job-name>`               | `Run CI`                                |
| App      | `<app-slug>:<status-name>` | `eclipse-eca-validation:eclipsefdn/eca` |
| Any      | `any:<status-name>`        | `any:Run CI`                            |

## Workflows as Required Status Checks

Given the following workflow `.github/workflows/ci.yaml` in a github repository:

```yaml
name: ci

on:
  pull_request:
    ...

jobs:
  build:
    ...
```

Now, as an example to protect the 'main' branch, add the required status check as below to
enforce that the `build` job has to pass before a pull request can be merged into it.

```jsonnet
orgs.newBranchProtectionRule('main') {
    required_status_checks+: [
        "build",
    ]
}
```
