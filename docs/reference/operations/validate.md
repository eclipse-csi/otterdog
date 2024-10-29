The `validate` operation will validate the local configuration on syntax and semantic level and provide feedback:

- Info: minor remarks, configuration can be applied, only visible when running with `-v`
- Warning: non-critical but configuration will not be applied as specified
- Error: critical, configuration can not be applied and need to be adapted

## Options

```shell
  --local            work in local mode, not updating the referenced default config
  -c, --config FILE  configuration file to use  [default: otterdog.json]
  -v, --verbose      enable verbose output (-vvv for more verbose output)
  -h, --help         Show this message and exit.
```

## Example

```shell
$ otterdog validate eclipse-csi -v

Validating organization configurations:

Organization technology.csi[id=eclipse-csi] (1/1)
╷
│ Info: org_secret[name="DEPENDENCY_TRACK_API_KEY"] will be skipped during processing:
│
│    only a dummy value '********' is provided in the configuration.
╵
╷
│ Error: repository[name="octopin"] has defined an invalid topic 'github actions'. Only lower-case, numbers and '-' are allowed characters.
╵
  Validation failed: 1 info(s), 0 warning(s), 1 error(s)
```
