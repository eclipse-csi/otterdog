## Build instructions
Create a virtual python environment and install necessary dependencies:
```console
$ make init
```

Additional system requirements:

* bitwarden cli tool (optional): install using `snap install bw`
* pass cli tool (optional): install using `apt install pass`
* jsonnet-bundler (mandatory): install using `go install -a github.com/jsonnet-bundler/jsonnet-bundler/cmd/jb@latest`

## Setup

The general configuration for supported organizations and their corresponding credentials in order
to access their GitHub settings has to be placed in a json file (default: __otterdog.json__, can be changed
with the __-c__ flag):

```json
{ 
  ...
  "organizations": [
    {
      "name": "<org name>",
      "github_id": "<github org id>",
      "credentials": {
        "provider": "<bitwarden | pass>",
        ... // provider specific data
      }
    }
  ]
  ...
}
```

## Credentials

Otterdog needs certain credentials to access information from an organization and its repositories on GitHub:

* username / password / 2FA seed 
* API token

The login / username / 2FA seed are required to access the web interface of GitHub in order to retrieve certain
settings that are not accessible via its rest / graphql API.

The GitHub api token needs to have the following scopes enabled:

* repo
* workflow
* admin:org
* admin:org_hook

The credentials can be stored in different providers (bitwarden, pass).

### Bitwarden

When using **bitwarden** to store the credentials, you need to enter a valid __item id__ as additional credential data:

```json
{ 
  ...
  "organizations": [
    {
      "name": "<org name>",
      "github_id": "<github org id>",
      "credentials": {
        "provider": "bitwarden",
        "item_id" : "<bitwarden item id>"
      }
    }
  ]
  ...
}
```

The item stored in bitwarden needs to contain the following information (a sample json output of such an item):

```json
{
  "object": "item",
  "id": "<bitwarden item id>",
  "name": "<item name>",
  "fields": [
    {
      "name": "api_token_admin",
      "value": "<github API token>"
    }
  ],
  "login": {
    "username": "<github username>",
    "password": "<github password>",
    "totp": "<github TOTP text code>"
  }
}
```

Mandatory items:

* Field with name "api_token_admin" and as value the GitHub token to access the organization
* __login.username__ of a user that can access the organization with enabled 2FA
* __login.password__ the password of that user
* __login.totp__ the TOTP text code

### Pass

When using **pass** to store the credentials, you need to enter fully qualified pass names to access the various
required credential data:

```json
{ 
  ...
  "organizations": [
    {
      "name": "<org name>",
      "github_id": "<github org id>",
      "credentials": {
        "provider": "pass",
        "api_token": "<path/to/api_token>",
        "username": "<path/to/username>",
        "password": "<path/to/password>",
        "2fa_seed": "<path/to/2fa_seed>"
      }
    }
  ]
  ...
}
```

In case your password storage dir is not located at the default location, you can
configurate that in the `defaults`:

```json
{
  "defaults": {
    "pass": {
      "password_store_dir": "path/to/storage/dir"
    }
  }
}
```

## Supported settings

### Organization Settings

| Field                                                    | Type            | Description                                               | Comment   |
|----------------------------------------------------------|-----------------|-----------------------------------------------------------|-----------|
| name                                                     | string or null  | Name of the organization                                  |           |
| billing_email                                            | string          | Billing email                                             |           |
| company                                                  | string or null  | Company name                                              |           |
| email                                                    | string or null  | Main contact point of the organization                    |           |
| twitter_username                                         | string or null  | Twitter username                                          |           |
| location                                                 | string or null  | Location                                                  |           |
| description                                              | string or null  | Description                                               |           |
| blog                                                     | string or null  | Url of the blog                                           |           |
| has_organization_projects                                | boolean         | If the organization can have projects                     |           |
| has_repository_projects                                  | boolean         | If the organization has repository projects               |           |
| default_repository_permission                            | string          | Default repository permissions                            |           |
| members_can_create_private_repositories                  | boolean         | If members can create private repos                       |           |
| members_can_create_public_repositories                   | boolean         | If members can create public repos                        |           |
| members_can_fork_private_repositories                    | boolean         | If members can fork private repos                         |           |
| web_commit_signoff_required                              | boolean         | If web commit signoff is required                         |           |
| members_can_create_pages                                 | boolean         | If members can create pages                               |           |
| members_can_create_public_pages                          | boolean         | If members can create public pages                        |           |
| dependabot_alerts_enabled_for_new_repositories           | boolean         | If dependabot alerts are enabled for new repos            |           |
| dependabot_security_updates_enabled_for_new_repositories | boolean         | If dependabot security updates are enabled for new repos  |           |
| dependency_graph_enabled_for_new_repositories            | boolean         | If dependency graph is enabled for new repos              |           |
| members_can_change_repo_visibility                       | boolean         | If members can change repo visibility                     |           |
| members_can_delete_repositories                          | boolean         | If members can delete repos                               |           |
| members_can_delete_issues                                | boolean         | If members can delete issues                              |           |
| readers_can_create_discussions                           | boolean or null | If readers can create discussions                         |           |
| members_can_create_teams                                 | boolean         | If members can create teams                               |           |
| two_factor_requirement                                   | boolean         | If two factor is required for all members                 | read-only |
| team_discussions_allowed                                 | boolean         | If team discussions are allowed                           |           |
| default_branch_name                                      | string          | The default branch name for repos                         |           |
| packages_containers_public                               | boolean         | If members can push public releases / containers          |           |
| packages_containers_internal                             | boolean         | If members can push private releases / containers         |           |
| organization_organization_projects_enabled               | boolean         | If members can create organization projects               |           |
| organization_members_can_change_project_visibility       | boolean         | If members can change visibility of organization projects |           |

### Repository Settings

| Field                           | Type           | Description                                                                         |
|---------------------------------|----------------|-------------------------------------------------------------------------------------|
| name                            | string         | Name of the repository                                                              |
| description                     | string or null | Project description                                                                 |
| homepage                        | string or null | Link to the homepage                                                                |
| private                         | boolean        | If the project is private                                                           |
| has_issues                      | boolean        | If the repo can have issues                                                         |
| has_projects                    | boolean        | If the repo can have projects                                                       |
| has_wiki                        | boolean        | If the repo has a wiki                                                              |
| default_branch                  | string         | Name of the default branch                                                          |
| allow_rebase_merge              | boolean        | If rebase merges are permitted                                                      |
| allow_merge_commit              | boolean        | If merge commits are permitted                                                      |
| allow_squash_merge              | boolean        | If squash merges are permitted                                                      |
| allow_auto_merge                | boolean        | If auto merges are permitted                                                        |
| delete_branch_on_merge          | boolean        | If branches shall automatically be deleted after a merge                            |
| allow_update_branch             | boolean        | If pull requests should suggest updates                                             |
| squash_merge_commit_title       | string         | Can be PR_TITLE or COMMIT_OR_PR_TITLE for a default squash merge commit title       |
| squash_merge_commit_message     | string         | Can be PR_BODY, COMMIT_MESSAGES, or BLANK for a default squash merge commit message |
| merge_commit_title              | string         | Can be PR_TITLE or MERGE_MESSAGE for a default merge commit title                   |
| merge_commit_message            | string         | Can be PR_BODY, PR_TITLE, or BLANK for a default merge commit message.              |
| archived                        | boolean        | If the repo is archived                                                             |
| allow_forking                   | boolean        | If the repo allows forking                                                          |
| web_commit_signoff_required     | boolean        | If the repo requires web commit signoff                                             |
| secret_scanning                 | string         | If secret scanning is "enabled" or "disabled"                                       |
| secret_scanning_push_protection | string         | If secret scanning push protection is "enabled" or "disabled"                       |
| dependabot_alerts_enabled       | boolean        | If the repo has dependabot alerts enabled                                           |
| branch_protection_rules         | array          | branch protection rules of the repo, see section below for details                  |

### Branch Protection Rules

| Field                        | Type            | Description                                                        |
|------------------------------|-----------------|--------------------------------------------------------------------|
| pattern                      | string          | Pattern to match branches                                          |
| allowsDeletions              | boolean         | If the branch can be deleted                                       |
| allowsForcePushes            | boolean         | If branch allows force pushes                                      |
| dismissesStaleReviews        | boolean         | Dismiss approved reviews automatically when a new commit is pushed |
| isAdminEnforced              | boolean         | Enforces status checks for admin                                   |
| lockAllowsFetchAndMerge      | boolean         | If the repo has dependabot alerts enabled                          |
| lockBranch                   | boolean         | If the branch is read-only                                         |
| requireLastPushApproval      | boolean         | TBD                                                                |
| requiredApprovingReviewCount | integer or null | TBD                                                                |
| requiresApprovingReviews     | boolean         | TBD                                                                |
| requiresCodeOwnerReviews     | boolean         | TBD                                                                |
| requiresCommitSignatures     | boolean         | TBD                                                                |
| requiresLinearHistory        | boolean         | TBD                                                                |
| requiresStatusChecks         | boolean         | TBD                                                                |
| requiresStrictStatusChecks   | boolean         | TBD                                                                |
| restrictsPushes              | boolean         | TBD                                                                |
| restrictsReviewDismissals    | boolean         | TBD                                                                |

## Usage

Run the **import** operation to retrieve the current live configuration for an organization:

```console
$ otterdog.sh import <organization>
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
* repo setting `secret_scanning_push_protection` seems to be only available for GitHub Enterprise billing, omitting for now