## Build instructions
Create virtual environment and install dependencies:
```console
$ make init
```

Run the **fetch** operation to retrieve the current live configuration for an organization:

```console
$ otterdog.sh fetch <organization>
```

The created configuration file for the organization can be found at `<data-directory>/orgs/<organization>.jsonnet`

Run the **plan** operation to highlight differences between the live configuration and the written configuration:

```console
$ otterdog.sh plan <organization>
```

Run **apply** operation to reflect the written configuration on github itself:

```console
$ otterdog.sh apply <organization>
```

## Known issues

### GraphQL
* branch protection rule property `blocksCreations` can not be updated via an update or create mutation, always seem to be `false`