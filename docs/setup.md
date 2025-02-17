# Quick Setup

To start using the cli part of `otterdog` right away on a specific organization you have to set up the following:

- define a default configuration to use, or use the following [default config](https://github.com/eclipse-csi/otterdog/blob/main/examples/template/otterdog-defaults.libsonnet) right away
- create a `otterdog.json` file that contains a list of GitHub organizations to manager and their respective credentials
- start managing your organizations using the cli

### Default configuration

The example [default config](https://github.com/eclipse-csi/otterdog/blob/main/examples/template/otterdog-defaults.libsonnet) has all supported features enabled and can be used right away.
However, it is advised to use a released tag instead of `main` to avoid incompatibilities.

### Otterdog configuration

Create a `otterdog.json` file with the following content (replace bracketed values according to your setup):

```json
{
  "defaults": {
    "jsonnet": {
      "base_template": "https://github.com/eclipse-csi/otterdog#examples/template/otterdog-defaults.libsonnet@main",
      "config_dir": "orgs"
    }
  },
  "organizations": [
    {
      "name": "<project-name>",
      "github_id": "<github-id>",
      "credentials": {
        "provider": "plain",
        "api_token": "<GitHub PAT>",
        "username": "<Username>",
        "password": "<Password>",
        "twofa_seed": "<2FA TOTP seed>"
      }
    }
  ]
}
```

The name of the configuration file can be freely chosen (can be overridden with the __-c__ flag).
However, when named `otterdog.json`, the cli tool will automatically detect and use that file if it is in the current working directory.

!!! warning

    In this example the `plain` provider is being used to access credentials to avoid setting up a `real` credential provider (see below) for a quick setup.
    However, the `plain` provider should *NOT* be used for anything else to avoid leakage of data in case the `otterdog.json` file is shared with other users.

### Credentials

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
* delete_repo

The credentials can be stored in different providers (bitwarden, pass).

#### Bitwarden

When using **bitwarden** to store the credentials, you need to enter a valid __item id__ as additional credential data:

```json
{
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

#### Pass

When using **pass** to store the credentials, you need to enter fully qualified pass names to access the various
required credential data:

```json
{
  "organizations": [
    {
      "name": "<org name>",
      "github_id": "<github org id>",
      "credentials": {
        "provider": "pass",
        "api_token": "<path/to/api_token>",
        "username": "<path/to/username>",
        "password": "<path/to/password>",
        "twofa_seed": "<path/to/2fa_seed>"
      }
    }
  ]
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

As the `password_store_dir` might be different on different machines, you can also customize that in a separate `.otterdog-defaults.json` file:

```json
{
  "pass": {
    "password_store_dir": "path/to/storage/dir"
  }
}
```
