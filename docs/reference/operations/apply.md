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
  --stats                 print the GitHub API usage statistics to stderr at the end  [env var: OTTERDOG_STATS]
  --stats-file FILE       write the GitHub API usage statistics as JSON to the given file  [env var:
                          OTTERDOG_STATS_FILE]
  --local                 work in local mode, not updating the referenced default config
  -c, --config FILE       configuration file to use  [default: otterdog.json]
  -v, --verbose           enable verbose output (-vvv for more verbose output)
  -f, --force             skips interactive approvals
  -n, --no-web-ui / --web-ui  skip settings retrieved via web ui, defaults to the
                              'no_web_ui' setting of the otterdog configuration
  --repo-filter TEXT      a valid shell pattern to match repository names to be included  [default: *]
  --update-webhooks       updates webhook with secrets regardless of changes
  --update-secrets        updates secrets regardless of changes
  --update-filter TEXT    a valid shell pattern to match webhook urls / secret names to be included for update
                          [default: *]
  -d, --delete-resources  enables deletion of resources if they are missing in the definition
  --delete-filter SELECTOR  only applies the deletions of the resources selected by their type, optionally
                            followed by their key as displayed by plan, using shell patterns, e.g.
                            'org_code_security_configuration' or 'org_code_security_configuration[name="Legacy*"]',
                            requires '--delete-resources', can be repeated
  -h, --help              Show this message and exit.
```

!!! note

    As otterdog does not maintain any local state, it can not determine if secret values need to be updated as
    GitHub will not disclose secret values via their APIs anymore after they have been set. As a consequence,
    `otterdog` will not update secret values by default unless `--update-secrets` or `--update-webhooks`
    has been specified.

## Deleting selected resources

`--delete-filter` turns `apply` into a targeted deletion: only the deletions of the resources it selects are
planned and applied. All the other changes, i.e. the additions, the modifications and the other deletions, are
skipped. They are neither displayed nor applied, only counted. The option requires `--delete-resources`, and can be
repeated to select more resources.

```shell
otterdog apply my-org --delete-resources --delete-filter org_code_security_configuration
```

```shell
  - remove org_code_security_configuration[name="Legacy - private/internal repositories"] {
    ...
  - }

  2 other change(s) are skipped, only the deletions selected by '--delete-filter' are applied.

  Do you want to perform these actions? (Only 'yes' or 'y' will be accepted to approve)
  ...
  Executed plan: 0 added, 0 changed, 1 deleted, 2 skipped.
```

### Selectors

A selector is written like the header of a resource in the output of `plan` and `apply`, so that a header can be
copied as is, e.g. `org_code_security_configuration[name="Legacy - private/internal repositories"]`:

- the type of the resource, e.g. `org_code_security_configuration`, `team_sync` or `repo_variable`, selects all
  the resources of this type
- optionally followed by conditions between brackets, separated by commas, each one naming either the key of the
  resource, e.g. `name` or `pattern`, or the type of its parent, e.g. `repository`

The type and the values are shell patterns, e.g. `org_*` or `name="Legacy*"`, matched with their case. A value is
quoted when it contains spaces, commas or brackets. Quote the whole selector in the shell:

| Selector | Deletes |
| --- | --- |
| `org_code_security_configuration` | all the code security configurations missing in the definition |
| `'org_code_security_configuration[name="Legacy*"]'` | the ones whose name starts with `Legacy` |
| `'org_code_security_configuration[name="Legacy - private/internal repositories"]'` | only this configuration |
| `'repo_variable[repository=my-repo]'` | the variables of the repository `my-repo` |
| `'branch_protection_rule[pattern="master", repository=jiro]'` | the rule for `master` of the repository `jiro` |
| `'org_*'` | the resources of the organization, e.g. its variables and secrets |

A selector that matches none of the resources to delete is reported with a warning, e.g. for a misspelled type or
a condition that names neither the key of the resource nor its parent. The planning takes the selection into
account, e.g. a team stays connected to an IdP group whose removal from `team_sync` is not selected.

As the other changes are skipped, the resources are selected, displayed and deleted with the current state of
their parent: the variables of a repository renamed with `aliases` are deleted in the repository with its current
name, and selected with `repository=<current name>`.

### Deleting resources in all organizations

Without organization, `apply` processes all the organizations of the otterdog configuration, one after the other,
and asks for approval for each organization that has a selected deletion:

```shell
otterdog apply --delete-resources --delete-filter 'org_code_security_configuration[name="Legacy*"]'
```

The organizations without a selected deletion report `No changes required.`, together with the warning above.
`--force` applies the deletions without asking for approval. Run the command without it first to review the
deletions of each organization: only `yes` or `y` approves them, answer `no` to cancel them.

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
