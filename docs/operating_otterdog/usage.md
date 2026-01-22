# Usage cli tool

In general, all operations act on the local configuration stored in `<cwd>/<config-dir>/<organization>/<organization>.jsonnet`.

A typical workflow to handle changes to an organization are as follows:

1. (first time) run an initial `import` of the organization
2. (first time) run an `apply` operation to create all resources already inherited from the default config (e.g. config repo)
3. (regular) fetch the latest config from the config repo using `fetch-config`
4. (optional) make any local changes to the configuration
5. (optional) run the `validate` operation to see if the configuration is syntactically and semantically correct
6. (optional) run the `plan` operation to see which changes would be applied taking the current live configuration into account
7. (regular) run the `apply` operation to actually apply the changes (also runs `validate` and `plan`, so steps 6 & 7 are redundant)
8. (regular) push the local configuration to the config repo using the `push-config` operation

!!! note

    It is not mandatory to store the configuration in the remote config repository (`<org>/.otterdog` by default).
    It could be stored anywhere else, however the operations `fetch-config` and `push-config` expect this repository to exist
    to function properly.
