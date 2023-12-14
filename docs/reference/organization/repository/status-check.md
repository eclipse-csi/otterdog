A [Branch Protection Rule](branch-protection-rule.md) allows to reference certain status checks
that are required to pass before a pull request can be merged into the target branch.

| Source   | Format                     | Example                                 |
|----------|----------------------------|-----------------------------------------|
| Workflow | `<status-name>`            | `Run CI`                                |
| App      | `<app-slug>:<status-name>` | `eclipse-eca-validation:eclipsefdn/eca` |
| Any      | `any:<status-name>`        | `any:Run CI`                            |
