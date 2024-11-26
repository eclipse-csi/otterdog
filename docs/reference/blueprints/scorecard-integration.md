# Scorecard Integration

This blueprint type ensure that a workflow is present that performs .

Furthermore, if actions are already pinned but the corresponding version in the comment does not matchup, this blueprint
will also correct the comment to the tag / branch that matches the used commit hash.

## Configuration

- `type` - `scorecard_integration`

### Settings

| Setting          | Necessity | Value type                     | Description                                                                  |
|------------------|-----------|--------------------------------|------------------------------------------------------------------------------|
| repo_selector    | optional  | [RepoSelector](#repo-selector) | If omitted, all repos are matched                                            |
| scorecard_action | optional  | string                         | the name of scorecard action to search for, default: 'ossf/scorecard-action' |
| workflow_name    | optional  | string                         | the name of the workflow to be added, default: 'scorecard-analysis.yml'      |
| workflow_content | mandatory | string                         | the workflow content to be added if no scorecard action can be found         |

#### Repo Selector

Allows to define a list of repositories that this blueprint should apply to.
The pattern is expected to be in [python regular expression format](https://docs.python.org/3/howto/regex.html).

| Setting      | Necessity  | Value type             |
|--------------|------------|------------------------|
| name_pattern | mandatory  | list[string] \| string |

### Templating

It is possible to use [Mustache](https://mustache.github.io/) logic-less templates within the workflow content of this blueprint.

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
| blueprint_id  | string | the id of the associated blueprint, e.g. `require-dependabot-auto-merge`                                                      |
| blueprint_url | string | the url of the associated blueprint, e.g. `https://github.com/eclipse-csi/.eclipsefdn/blob/main/otterdog/blueprints/test.yml` |

## Example

``` yaml
id: scorecard-integration
name: Integrate OSSF Scorecard anaylsis
description: |-
  Integrate OSSF Scorecard analysis.
type: scorecard_integration
config:
  repo_selector:
    name_pattern:
      - repoA
      - repoB
  workflow_name: scorecard-analysis.yml
  workflow_content: |
    name: Scorecard analysis workflow
    on:
      push:
        branches:
        - main
      schedule:
        # Weekly on Saturdays.
        - cron:  '30 1 * * 6'

    permissions: read-all

    jobs:
      analysis:
        if: github.repository_owner == '{{github_id}}'
        name: Scorecard analysis
        runs-on: ubuntu-latest
        permissions:
          security-events: write
          id-token: write

        steps:
          - name: "Checkout code"
            uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
            with:
              persist-credentials: false

          - name: "Run analysis"
            uses: ossf/scorecard-action@62b2cac7ed8198b15735ed49ab1e5cf35480ba46 # v2.4.0
            with:
              results_file: results.sarif
              results_format: sarif
              publish_results: true
```
