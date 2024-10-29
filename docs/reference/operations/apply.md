The `apply` operation will apply changes of the local configuration to the current live settings on GitHub.

When the `apply` operation is executed, the following happens:

- the local configuration is [validated](validate.md)
- the current live configuration is retrieved
- the current changes are [planned](plan.md)
- if approved, the changes are applied

!!! note

    In general, resources that are present on GitHub but not contained in the local configuration are marked
    for deletion, however, by default `otterdog` will not remove any resources unless the option `--delete-resources`
    has been specified.

## Options

```shell
  --local                 work in local mode, not updating the referenced default config
  -c, --config FILE       configuration file to use  [default: otterdog.json]
  -v, --verbose           enable verbose output (-vvv for more verbose output)
  -f, --force             skips interactive approvals
  -n, --no-web-ui         skip settings retrieved via web ui
  --repo-filter TEXT      a valid shell pattern to match repository names to be included  [default: *]
  --update-webhooks       updates webhook with secrets regardless of changes
  --update-secrets        updates secrets regardless of changes
  --update-filter TEXT    a valid shell pattern to match webhook urls / secret names to be included for update
                          [default: *]
  -d, --delete-resources  enables deletion of resources if they are missing in the definition
  -h, --help              Show this message and exit.
```

!!! note

    As otterdog does not maintain any local state, it can not determine if secret values need to be updated as
    GitHub will not disclose secret values via their APIs anymore after they have been set. As a consequence,
    `otterdog` will not update secret values by default unless `--update-secrets` or `--update-webhooks`
    has been specified.

## Example

```shell
$ otterdog apply adoptium

Apply changes for configuration at '.../otterdog-configs/otterdog.json'

Actions are indicated with the following symbols:
  + create
  ~ modify
  ! forced update
  - delete

Organization adoptium[id=adoptium]
  there have been 4 validation infos, enable verbose output with '-v' to to display them.

  ~ settings {
    ~ name                        = "Eclipse Adoptium" -> "Eclipse Adoptium Project"
    }

  - remove repository[name="Incubator"] {
    - allow_auto_merge            = False
    - allow_forking               = True
    - allow_merge_commit          = True
    - name                        = "Incubator"
    ...
  - }

  + add repository[name="Incubator-New"] {
    + allow_auto_merge            = False
    + allow_forking               = True
    + name                        = "Incubator-New"
    ...
  + }

  No resource will be removed, use flag '--delete-resources' to delete them.
```
