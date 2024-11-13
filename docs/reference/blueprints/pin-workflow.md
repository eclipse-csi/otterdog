# Pin Workflow

This blueprint type will pin any encountered GitHub action or reusable workflow in any used workflow of matching repositories
to the commit hash of the latest released version that corresponds to the currently used reference.

Furthermore, if actions are already pinned but the corresponding version in the comment does not matchup, this blueprint
will also correct the comment to the tag / branch that matches the used commit hash.

## Example

A workflow uses the `actions/checkout` action with reference `v3`. This action will be pinned to the commit hash of
the latest corresponding release `v3.6.0`.

``` diff
     steps:
     - name: Checkout code
-      uses: actions/checkout@v3
+      uses: actions/checkout@f43a0e5ff2bd294095638e18286ca9a3d1956744 # v3.6.0
```

## Configuration

- `type` - `pin_workflow`

### Settings

| Setting       | Necessity | Value type                         | Description                       |
|---------------|-----------|------------------------------------|-----------------------------------|
| repo_selector | optional  | [RepoSelector](#repo-selector)     | If omitted, all repos are matched |

#### Repo Selector

Allows to define a list of repositories that this blueprint should apply to.
The pattern is expected to be in [python regular expression format](https://docs.python.org/3/howto/regex.html).

| Setting      | Necessity  | Value type             |
|--------------|------------|------------------------|
| name_pattern | mandatory  | list[string] \| string |

### Skipping pinning

By default, any action using `main` or `master` as reference will be skipped. In case an action can not be pinned
as it is required to be used with a specific tag or branch (e.g. [slsa-github-generator](https://github.com/slsa-framework/slsa-github-generator))
you can add a comment to the action:

``` yaml
    uses: slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@v2.0.0 # ignore: pin
```

## Example

``` yaml
id: pin-workflows
name: Pin GitHub actions in workflows
description: |-
  This blueprint pins GitHub actions used in workflows to their corresponding commit hash.
type: pin_workflow
config:
```
