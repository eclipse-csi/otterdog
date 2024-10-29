The `import` operation will retrieve the current live settings for the specified GitHub organization and store
them locally in a file `<github-id>/<github-id>.jsonnet` in the organization specific working directory.

## Options

```shell
  -c, --config FILE  configuration file to use  [default: otterdog.json]
  -f, --force        skips interactive approvals
  -n, --no-web-ui    skip settings retrieved via web ui

  --local            work in local mode, not updating the referenced default config

  -v, --verbose      enable verbose output (-vvv for more verbose output)
  -h, --help         Show this message and exit.
```

!!! note

    If the organization contains some secret values, e.g. webhooks with secrets, or organization / repository secrets,
    already resolved secret values in the existing configuration file will be copied over to the newly imported.

## Example

```shell
$ otterdog import adoptium -f

Importing resources for configuration at '.../otterdog-configs/otterdog.json'

Organization adoptium[id=adoptium]

Existing definition copied to '.../otterdog-configs/orgs/adoptium/adoptium.jsonnet.bak'.

  Copying secrets from previous configuration.
  Organization definition written to '.../otterdog-configs/orgs/adoptium/adoptium.jsonnet'.
```
