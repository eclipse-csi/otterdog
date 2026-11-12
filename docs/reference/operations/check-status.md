The `check-status` operation tells for each organization whether its configuration is valid and in sync with the
live settings on GitHub, without displaying the differences. It is meant for scripts and dashboards that check many
organizations, e.g. all the organizations of the otterdog configuration when no organization is given.

When the `check-status` operation is executed, the following happens:

- the local configuration is [validated](validate.md), the live settings are not retrieved if validation errors are
  found
- the current live configuration is retrieved and compared to the local configuration, like [plan](plan.md) does
- the status of the organization is displayed, and written as JSON once all the organizations are checked if
  `--json` is given

The status of an organization consists of:

| Status          | Description                                                                                    |
|-----------------|------------------------------------------------------------------------------------------------|
| Archived        | whether the organization is archived on GitHub                                                 |
| Validation      | whether the configuration is valid: no validation warning or error, validation infos are ignored |
| Synchronization | whether the configuration is in sync: valid, and no resource to add, change or delete          |

As the differences are counted but not displayed, use [plan](plan.md) to display them. Secrets are not resolved, so
the operation does not need the credentials of the secrets referenced by the configuration.

!!! note

    `check-status` is the CLI counterpart of the check of a pull request by the GitHub App (`/otterdog check-sync`),
    which compares the configuration of the default branch of the configuration repository to the live settings.
    To check the same configuration, fetch it first with `otterdog fetch-config`.

    The GitHub App considers the configuration in sync as long as there is no change, while `check-status` also
    requires the configuration to be free of validation warnings.

## Options

```shell
  --stats                     print the GitHub API usage statistics to stderr at the end  [env var: OTTERDOG_STATS]
  --stats-file FILE           write the GitHub API usage statistics as JSON to the given file  [env var:
                              OTTERDOG_STATS_FILE]
  --local                     work in local mode, not updating the referenced default config
  -c, --config FILE           configuration file to use. Default: otterdog.jsonnet, otterdog.json
  -v, --verbose               enable verbose output (-vvv for more verbose output)
  -n, --no-web-ui / --web-ui  skip settings retrieved via web ui, defaults to the 'no_web_ui' setting of the
                              otterdog configuration
  -r, --repo-filter TEXT      a valid shell pattern to match repository names to be included  [default: *]
  -j, --json FILE             a file to write the status as JSON output
  -h, --help                  Show this message and exit.
```

## Example

```shell
$ otterdog check-status my-org my-other-org --no-web-ui --json status.json

Project my-project[github_id=my-org]
  Archived: False
  Validation status: True
  Synchronization status: False

Project my-other-project[github_id=my-other-org]
  Archived: False
  Validation status: True
  Synchronization status: True
```

The file `status.json` contains the status of every organization, `changes` being the number of settings to change:

```json
[
  {
    "org_id": "my-org",
    "is_archived": false,
    "validation_status": {
      "is_valid": true,
      "infos": 0,
      "warnings": 0,
      "errors": 0
    },
    "sync_status": {
      "in_sync": false,
      "additions": 1,
      "changes": 2,
      "deletions": 0
    }
  },
  {
    "org_id": "my-other-org",
    "is_archived": false,
    "validation_status": {
      "is_valid": true,
      "infos": 0,
      "warnings": 0,
      "errors": 0
    },
    "sync_status": {
      "in_sync": true,
      "additions": 0,
      "changes": 0,
      "deletions": 0
    }
  }
]
```
