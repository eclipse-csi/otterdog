# Required File

This blueprint type ensures that one or more files are present in the repositories that match this blueprint.
Depending on the `strict` setting, it will be checked whether the file already exists or if it exactly matches the
configured `content`.

## Configuration

- `type` - `required_file`

### Settings

| Setting       | Necessity | Value type                         |
|---------------|-----------|------------------------------------|
| repo_selector | mandatory | [RepoSelector](#repo-selector)     |
| files         | mandatory | list[[FileSetting](#file-setting)] |

#### Repo Selector

Allows to define a list of repositories that this blueprint should apply to.
The pattern is expected to be in [python regular expression format](https://docs.python.org/3/howto/regex.html).

| Setting      | Necessity  | Value type   |
|--------------|------------|--------------|
| name_pattern | mandatory  | list[string] |

#### File setting

| Setting | Necessity  | Value type | Description                                                                                               |
|---------|------------|------------|-----------------------------------------------------------------------------------------------------------|
| path    | mandatory  | string     | the path of the file within the repository without leading slash                                          |
| content | mandatory  | string     | the content of the file                                                                                   |
| strict  | optional   | boolean    | if `false` (default), the file will be only checked for existence, otherwise the content will be compared |

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
        name: Dependabot auto-merge
        on: pull_request_target

        permissions: read-all

        jobs:
          dependabot:
            permissions:
              contents: write
              pull-requests: write
            uses: adoptium/.github/.github/workflows/dependabot-auto-merge.yml@main
      # ensure that changes to the template are propagated
      strict: true
```
