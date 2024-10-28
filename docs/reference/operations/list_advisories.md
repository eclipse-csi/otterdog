# List Advisories

The `list_advisories` operation lists the repository security advisories in a given organization, with the ability to filter by the state of the advisories.

## Options

```shell
  --state [triage|draft|published|closed]  filter advisories by state [default: None]
  -c, --config FILE          configuration file to use  [default: otterdog.json]
  --local                    work in local mode, not updating the referenced default config
  -v, --verbose              enable verbose output (-vvv for more verbose output)
  -h, --help                 Show this message and exit.
```

## Example

```shell
$ otterdog list_advisories eclipse-csi --state published

Listing repository security advisories:

Organization technology.csi[id=eclipse-csi]
Found 2 advisories with state 'published'.

advisory['GHSA-xxxx-xxxx-xxxx']
  - id: GHSA-xxxx-xxxx-xxxx
  - state: published
  - description: Example advisory description
  - created_at: 2023-01-01T00:00:00Z
  - updated_at: 2023-01-02T00:00:00Z

advisory['GHSA-yyyy-yyyy-yyyy']
  - id: GHSA-yyyy-yyyy-yyyy
  - state: published
  - description: Another example advisory description
  - created_at: 2023-01-03T00:00:00Z
  - updated_at: 2023-01-04T00:00:00Z
```
