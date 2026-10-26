The `plan` operation shows the changes that an [apply](apply.md) operation would perform, without changing anything
on GitHub.

When the `plan` operation is executed, the following happens:

- the local configuration is [validated](validate.md), planning is aborted if validation errors are found
- the current live configuration is retrieved
- the differences between the local and the live configuration are displayed

Resources that exist on GitHub but are missing in the local configuration are displayed as deletions. Whether
they are actually deleted depends on how the changes are applied, see [Apply](apply.md).

## Options

```shell
  --stats                 print the GitHub API usage statistics to stderr at the end  [env var: OTTERDOG_STATS]
  --stats-file FILE       write the GitHub API usage statistics as JSON to the given file  [env var:
                          OTTERDOG_STATS_FILE]
  --local                 work in local mode, not updating the referenced default config
  -c, --config FILE       configuration file to use. Default: otterdog.jsonnet, otterdog.json
  -v, --verbose           enable verbose output (-vvv for more verbose output)
  -n, --no-web-ui         skip settings retrieved via web ui
  -r, --repo-filter TEXT  a valid shell pattern to match repository names to be included  [default: *]
  --update-webhooks       updates webhook with secrets regardless of changes
  --update-secrets        updates secrets regardless of changes
  --only-secrets          only updates secrets
  --update-filter TEXT    a valid shell pattern to match webhook urls / secret names to be included for update
                          [default: *]
  -h, --help              Show this message and exit.
```

## Example

```shell
$ otterdog plan my-org --repo-filter my-repo

Planning execution:

Actions are indicated with the following symbols:
  + create
  ~ modify
  ! forced update
  - delete

Organization my-org[id=my-org]

  ~ repository[name="my-repo"] {
  ~   has_wiki = true -> false
  ~ }

  + add repo_ruleset[name="default-branch", repository="my-repo"] {
  +   allows_creations = false
  +   allows_deletions = false
  ...
  + }

Plan: 1 to add, 1 to change, 0 to delete.
```
