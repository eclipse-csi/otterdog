# Required File

This blueprint type ensures that one or more files are present in the repositories that match this blueprint.
Depending on the `strict` setting, it will be checked whether the file already exists or if it exactly matches the
configured `content`.

## Configuration

- `type` - `required_file`

### Settings

| Setting       | Necessity | Value type                         | Description                       |
|---------------|-----------|------------------------------------|-----------------------------------|
| repo_selector | optional  | [RepoSelector](#repo-selector)     | If omitted, all repos are matched |
| files         | mandatory | list[[FileSetting](#file-setting)] |                                   |

#### Repo Selector

Allows to define a list of repositories that this blueprint should apply to.
The pattern is expected to be in [python regular expression format](https://docs.python.org/3/howto/regex.html).

| Setting      | Necessity  | Value type             |
|--------------|------------|------------------------|
| name_pattern | mandatory  | list[string] \| string |

#### File setting

| Setting | Necessity  | Value type | Description                                                                                               |
|---------|------------|------------|-----------------------------------------------------------------------------------------------------------|
| path    | mandatory  | string     | the path of the file within the repository without leading slash                                          |
| content | mandatory  | string     | the content of the file                                                                                   |
| strict  | optional   | boolean    | if `false` (default), the file will be only checked for existence, otherwise the content will be compared |

### Templating

It is possible to use [Mustache](https://mustache.github.io/) logic-less templates within the content of a blueprint.

To use a context variable, simply enclose its name in curly braces:

```yaml
  This is an example to use mustache template for repo: {{repo_name}}
```

In this example, `{{repo_name}}` will be replaced with the actual name of the repository being processed. For more complex examples please refer
to the [mustache documentation](https://mustache.github.io/mustache.5.html).


#### Template Context

The following context is injected during template evaluation when a specific repository is being processed:

| Variable      | Type   | Description                                                                                                                   |
|---------------|--------|-------------------------------------------------------------------------------------------------------------------------------|
| project_name  | string | the project name of the associated GitHub organization, e.g. `technology.csi`                                                 |
| github_id     | string | the name of the associated GitHub organization                                                                                |
| repo_name     | string | the name of the repository being processed                                                                                    |
| org           | dict   | the [organization settings](../organization/settings.md) for the associated GitHub organization                               |
| repo          | dict   | the [repository settings](../organization/repository/index.md) for the repository being processed                             |
| repo_url      | string | the url of the repository being processed, e.g. `https://github.com/eclipse-csi/otterdog`                                     |
| blueprint_url | string | the url of the associated blueprint, e.g. `https://github.com/eclipse-csi/.eclipsefdn/blob/main/otterdog/blueprints/test.yml` |

## Example

In this example a workflow file `.github/workflows/dependabot-auto-merge.yml` should be present in a set of repositories matching the configured content.

``` yaml
id: require-dependabot-auto-merge
name: Require dependabot-auto-merge.yml
type: required_file
config:
  repo_selector:
    name_pattern:
      - temurin-build
      - containers
  files:
    - path: .github/workflows/dependabot-auto-merge.yml
      content: |
        # This is a templated file from {{blueprint_url}} for {{repo_name}}
        name: Dependabot auto-merge
        on: pull_request_target

        permissions: read-all

        jobs:
          dependabot:
            permissions:
              contents: write
              pull-requests: write
            uses: {{github_id}}/.github/.github/workflows/dependabot-auto-merge.yml@main
      # ensure that changes to the template are propagated
      strict: true
```
