## Build instructions
Create a virtual python environment and install necessary dependencies:
```console
$ make init
```

Additional system requirements:

* bitwarden cli tool: install using `snap install bw`
* jsonnet-bundler: install using `go install -a github.com/jsonnet-bundler/jsonnet-bundler/cmd/jb@latest`

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
        "provider": "bitwarden",
        "item_id" : "<bitwarden item id>"
      }
    }
  ]
  ...
}
```

When using **bitwarden** to store the credentials, you need to enter a valid __item id__. This item needs to
contain the following information (a sample json output of such an item):

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

The login / username / totp are required to access the web interface of GitHub in order to retrieve certain
settings that are not accessible via its rest / graphql API.

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