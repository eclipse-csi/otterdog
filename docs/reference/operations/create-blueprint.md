# Create Blueprint

Scaffolds a [blueprint](../blueprints/index.md) definition at `otterdog/blueprints/<id>.yml` and validates it against the
blueprint model. No GitHub access is needed; the file is written into a local checkout of the configuration repository
and committed as a normal pull request.

```shell
otterdog create-blueprint --type required_file --blueprint-id require-build-workflow \
    --filter '^org\.osgi\.annotation$' \
    --root ~/git/org.osgi.annotation --from ~/git/org.osgi.annotation/.github/workflows/build.yml \
    --output ~/git/.eclipsefdn
```

| Option            | Description                                                                                         |
|-------------------|-----------------------------------------------------------------------------------------------------|
| `--type`          | `required_file`, `pin_workflow`, `append_configuration` or `scorecard_integration`                   |
| `--blueprint-id`  | id of the blueprint, also the file name                                                             |
| `--filter`        | regular expression for `repo_selector.name_pattern`; omitted: the blueprint applies to all repos    |
| `--from`          | local file whose content becomes a `files` entry (`required_file`) or the workflow (`scorecard_integration`); repeatable |
| `--root`          | directory the `--from` paths are relative to, which determines the path inside the repositories     |
| `--output`        | checkout of the configuration repository to write into                                              |
| `--force`         | overwrite an existing file                                                                          |

The same scaffolding is available as the comment command `/otterdog create blueprint`, see
[comment commands](../blueprints/commands.md).
