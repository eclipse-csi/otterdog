The following format is supported to match branches to be included / excluded in repository rulesets:

| Description                 | Format              | Example                                         |
|-----------------------------|---------------------|-------------------------------------------------|
| match individual branch(es) | `refs/heads/<name>` | `refs/heads/main` or `refs/heads/releases/**/*` |
| match the default branch    | `~DEFAULT_BRANCH`   | `~DEFAULT_BRANCH`                               |
| match all branches          | `~ALL`              | `~ALL`                                          |
