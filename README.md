## Build instructions
Create virtual environment and install dependencies:
```console
$ make init
```

Run the fetch operation to retrieve the current live configuration for an organization:

```console
$ otterdog.sh fetch <organization> -v
```

The created configuration file for the organization can be found at `<data-directory>/orgs/<organization>.jsonnet`

Run verify operation to highlight differences between the live configuration and the written configuration:

```console
$ otterdog.sh verify <organization> -v
```

Run update operation to reflect the written configuration on github itself:

```console
$ otterdog.sh update <organization> -v
```

## Known issues

### Rest API
* organization setting `dependency_graph_enabled_for_new_repositories` gets automatically enabled when either enabling `dependabot_alerts_enabled_for_new_repositories` or `dependabot_security_updates_enabled_for_new_repositories`

### GraphQL
* branch protection rule property `blocksCreations` can not be updated via an update or create mutation, always seem to be `false`