A BranchOrTag represents either a branch or tag pattern to use within an [Environment](environment.md).
The following format is used to distinguish between tags and branches:

| Type   | Format          | Example                  |
|--------|-----------------|--------------------------|
| Branch | `<pattern>`     | `main`                   |
| Tag    | `tag:<pattern>` | `tag:v[0-9].[0-9].[0.9]` |
