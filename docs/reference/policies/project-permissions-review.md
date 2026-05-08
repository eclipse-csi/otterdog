# Project Permissions Review

This policy creates periodic GitHub issues to review maintainer and collaborator permissions for repositories and related services.

## Configuration

- `type` - `project_permissions_review`

### Settings

| Setting           | Necessity | Value type    | Description                                                                |
|-------------------|-----------|---------------|----------------------------------------------------------------------------|
| workflow_filter   | mandatory | string        | Only consider workflow runs that reference the specified workflows         |
| issue_title       | optional  | string        | Title for the created GitHub issues (default: "Periodic Review: Project Permissions") |
| artifact_name     | optional  | string        | Name of artifact containing custom issue content (as JSON with "title" and "body" fields) |

## How it works

1. A scheduled workflow runs in a repository (triggered by cron schedule or manually)
2. The workflow calls a reusable workflow matching the `workflow_filter` pattern
3. When the workflow completes successfully, the policy is triggered
4. A new issue is created with the configured content

## Issue Content

The policy can use custom issue content from two sources (checked in this order):

1. **Workflow Artifact** (recommended): If `artifact_name` is configured, the policy will download an artifact containing a `content.json` file with `title` and/or `body` fields
2. **Repository File**: If no artifact is found, it will look for `.github/project-permissions-review-body.md` in your repository

If neither is found, a simple default issue body will be generated with:
- The current year and a basic review prompt
- A note that the issue was automatically generated

## Example

```yaml
name: Project Permissions Review
description: |-
  Automatically create annual issues to review repository maintainers,
  collaborators, and package registry access.
type: project_permissions_review
config:
  workflow_filter: ".*/project-permissions-review.yml.*"
  issue_title: "Annual Security Review: Project Permissions"
  artifact_name: "project-permissions-review-content"
```

## Reusable Workflow

Create a reusable workflow in your `.otterdog` config repository (e.g., `.otterdog/workflows/.github/workflows/project-permissions-review.yml`):

```yaml
name: Project Permissions Review

on:
  workflow_call:
    inputs:
      issue_title:
        description: 'Custom issue title'
        required: false
        type: string
      issue_body:
        description: 'Custom issue body in markdown format'
        required: false
        type: string

jobs:
  trigger-review:
    runs-on: ubuntu-latest
    steps:
      - name: Run Project Permissions Review
        run: |
          echo "Project Permissions Review"

      - name: Create content artifact
        if: inputs.issue_title != '' || inputs.issue_body != ''
        run: |
          mkdir -p artifact
          cat > artifact/content.json <<'EOF'
          {
            "title": "${{ inputs.issue_title }}",
            "body": ${{ toJSON(inputs.issue_body) }}
          }
          EOF

      - name: Upload content artifact
        if: inputs.issue_title != '' || inputs.issue_body != ''
        uses: actions/upload-artifact@65c4c4a1ddee5b72f698fdd19549f0f0fb45cf08
        with:
          name: project-permissions-review-content
          path: artifact/
```

## Usage in Repositories

### Basic Usage (Default Content)

In your repository, create a scheduled workflow (e.g., `.github/workflows/project-review.yml`):

```yaml
name: Project Permissions Review

on:
  schedule:
    # Run annually on January 1st at 10:00 AM UTC
    - cron: '0 10 1 1 *'
  workflow_dispatch:

jobs:
  review-project-permissions:
    uses: <org>/.otterdog/workflows/.github/workflows/project-permissions-review.yml@main
```

Replace `<org>` with your organization name (e.g., `otterdog-kairoaraujo`).

### With Custom Title and Body

To provide custom issue content directly in the workflow:

```yaml
name: Project Permissions Review

on:
  schedule:
    # Run annually on January 1st at 10:00 AM UTC
    - cron: '0 10 1 1 *'
  workflow_dispatch:

jobs:
  review-project-permissions:
    uses: <org>/.otterdog/workflows/.github/workflows/project-permissions-review.yml@main
    with:
      issue_title: "Annual Security Review: Project Permissions"
      issue_body: |
        ## Project Permissions Review

        This is a periodic review to ensure that access permissions for this repository and related services remain appropriate and secure.

        ### Objectives

        1. **Review Current Access**: Verify that all maintainers/commiters and collaborators still require their current level of access
        2. **Evaluate Activity**: Check recent contribution activity to ensure accounts are active
        3. **Security Audit**: Remove unused or unnecessary permissions


        - [ ] Verify all maintainers are still active contributors
        - [ ] Confirm admin access is limited to those who need it
        - [ ] Remove accounts that are no longer active in the project
        - [ ] Review Access to Project publishes packages registries (i.e: PyPI, NPM, Maven, etc)
        - [ ] Verify two-factor authentication is enabled for all maintainers
        - [ ] Update MAINTAINERS or similar documentation files
```
