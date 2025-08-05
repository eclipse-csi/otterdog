A BranchOrTag represents either a branch or tag pattern to use within an [Environment](environment.md).
The following format is used to distinguish between tags and branches:

| Type   | Format          | Example       |
|--------|-----------------|---------------|
| Branch | `<pattern>`     | `main`        |
| Tag    | `tag:<pattern>` | `tag:v[0-9]*` |

For more information about the pattern matching syntax, see the 
[Ruby File.fnmatch documentation](https://ruby-doc.org/current/File.html#method-c-fnmatch).
