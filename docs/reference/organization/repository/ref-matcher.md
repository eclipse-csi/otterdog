The following formats are supported to match the refs to be included / excluded in rulesets, depending on the
`target` of the ruleset:

| Target            | Description                 | Format              | Example                                         |
|-------------------|-----------------------------|---------------------|-------------------------------------------------|
| `branch`, `push`  | match individual branch(es) | `refs/heads/<name>` | `refs/heads/main` or `refs/heads/releases/**/*` |
| `branch`, `push`  | match the default branch    | `~DEFAULT_BRANCH`   | `~DEFAULT_BRANCH`                               |
| `branch`, `push`  | match all branches          | `~ALL`              | `~ALL`                                          |
| `tag`             | match individual tag(s)     | `refs/tags/<name>`  | `refs/tags/v1.0.0` or `refs/tags/v*`            |
| `tag`             | match all tags              | `~ALL`              | `~ALL`                                          |

Names and patterns follow the `fnmatch` syntax, in which `*` does not match `/`, see
[Using fnmatch syntax](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository#using-fnmatch-syntax).

## Validation rules

- specifying a pattern that does not match the formats supported for the `target` of the ruleset triggers an error
