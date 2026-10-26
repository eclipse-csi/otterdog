# Setup Otterdog

*After completing the [installation of Otterdog](install.md), you need to perform some additional steps to configure otterdog.*

To start using the cli part of `otterdog` right away on a specific organization you have to set up the following:

- define a default configuration to use, or use the following [default config](https://github.com/eclipse-csi/otterdog/blob/main/examples/template/otterdog-defaults.libsonnet) right away
- create a `otterdog.json` file that contains a list of GitHub organizations to manager and their respective credentials
- start managing your organizations using the cli

### Default configuration

The example [default config](https://github.com/eclipse-csi/otterdog/blob/main/examples/template/otterdog-defaults.libsonnet) has all supported features enabled and can be used right away.
However, it is advised to use a released tag instead of `main` to avoid incompatibilities.

A change of the default configuration applies to all the organizations using it. Its impact can be evaluated
beforehand on the **Template impact** page of the administration of the otterdog dashboard: the files of the default
configuration are edited there, and the configurations of the projects are evaluated with the edited files. The page
groups the changes by property across the projects, e.g. `repositories[*].delete_branch_on_merge` changed from `true` to
`false` in 807 repositories of 269 projects, and lists the projects whose configuration changes, with their changes,
and the ones whose configuration fails to evaluate. The configurations are the ones fetched by the dashboard, and are
evaluated in the browser.

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

### Cost policy

Pull requests that may incur costs cannot be auto-merged and require a review by the designated team.
The thresholds used for this check can be adjusted in the `defaults` of the `otterdog.json` file:

```json
{
  "defaults": {
    "cost_policy": {
      "free_max_cache_size_gb": 10
    }
  }
}
```

| Key                      | Default | Description                                                                                                                  |
|--------------------------|---------|------------------------------------------------------------------------------------------------------------------------------|
| `free_max_cache_size_gb` | `10`    | GitHub Actions cache size limit (in GB) included free of charge, adding a repository with a `max_cache_size_gb` above this value is considered cost-related |

Any change of `max_cache_size_gb` on an existing repository or organization is always considered cost-related.

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

The credentials can be stored in different providers (bitwarden, pass, vault, env).

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
    "totp": "<github 2FA TOTP seed>"
  }
}
```

Mandatory items:

* Field with name "api_token_admin" and as value the GitHub token to access the organization
* __login.username__ of a user that can access the organization with enabled 2FA
* __login.password__ the password of that user
* __login.totp__ the 2FA TOTP seed

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

#### HashiCorp Vault

When using a **HashiCorp Vault** to store the credentials, the secrets are read from a KV version 2 secrets engine.
Each credential is referenced as `<path/to/secret>/<field>`, the last component being the name of the field:

```json
{
  "organizations": [
    {
      "name": "<org name>",
      "github_id": "<github org id>",
      "credentials": {
        "provider": "vault",
        "api_token": "<path/to/secret>/<field>",
        "username": "<path/to/secret>/<field>",
        "password": "<path/to/secret>/<field>",
        "twofa_seed": "<path/to/secret>/<field>"
      }
    }
  ]
}
```

The connection to the Vault is configured in the `defaults`:

```json
{
  "defaults": {
    "vault": {
      "vault_addr": "https://vault.example.org",
      "mount_point": "<kv mount point>",
      "verify_ssl": true
    }
  }
}
```

| Key                  | Description                                                                                                       |
|----------------------|-------------------------------------------------------------------------------------------------------------------|
| `vault_addr`         | the address of the Vault, defaults to the environment variable `VAULT_ADDR`                                       |
| `vault_token`        | the token to use, defaults to the environment variable `VAULT_TOKEN`, then to the file `~/.vault-token`; if no valid token is found, otterdog asks to log in interactively |
| `mount_point`        | the mount point of the KV secrets engine, it is recommended to always set it                                      |
| `verify_ssl`         | whether to verify the TLS certificate of the Vault, disabled by default; enable it, or set `ca_cert`              |
| `ca_cert`            | path to a CA certificate bundle used to verify the TLS certificate of the Vault                                   |
| `client_cert`        | path to a client certificate for mutual TLS                                                                       |
| `batch_mode`         | if `true`, fail instead of asking to log in interactively, e.g. in automation                                     |
| `api_token_pattern`, `username_pattern`, `password_pattern`, `twofa_seed_pattern` | patterns of the credential paths used when an organization does not specify them, `{0}` is replaced by the name of the organization |

#### Environment based credentials

When using environment variables to store the credentials, you need to set the following environment variables:

```json
{
  "organizations": [
    {
      "name": "<org name>",
      "github_id": "<github org id>",
      "credentials": {
        "provider": "env",
        "api_token": "<env_var_which_contains_api_token>",
        "username": "<env_var_which_contains_username>",
        "password": "<env_var_which_contains_password>",
        "twofa_seed": "<env_var_which_contains_2fa_seed>"
      }
    }
  ]
}
```

The environment variables need to be set in the system where otterdog is executed.
They can also be set in a `.env` file in the current working directory, which will be automatically loaded by otterdog.

If you want to keep the same environment variable pattern across organizations, you can set defaults and use placeholders in the `defaults.env` section. The env provider normalizes placeholder values by converting them to uppercase and replacing spaces and hyphens with underscores. You can use `{org_name}` and `{github_id}`.

```json
{
  "defaults": {
    "credentials": {
      "provider": "env"
    },
    "env": {
      "api_token": "OTTER_{org_name}_API_TOKEN",
      "username": "OTTER_{org_name}_USERNAME",
      "password": "OTTER_{github_id}_PASSWORD",
      "twofa_seed": "OTTER_{github_id}_TOTP_SEED"
    }
  }
}
```

Hint: You can combine this provider with GitHub Actions secrets to securely store the credentials in a GitHub repository and use them in a GitHub action that runs otterdog:

```yaml
  env:
    OTTER_USERNAME: ${{ vars.OTTER_USERNAME }}
    OTTER_PASSWORD: ${{ secrets.OTTER_PASSWORD }}
    OTTER_TOTP_SEED: ${{ secrets.OTTER_TOTP_SEED }}
    OTTER_API_TOKEN: ${{ secrets.OTTER_API_TOKEN }}
```

### Environment variables

The cli of otterdog reads the following environment variables:

| Variable               | Description                                                                                                                                                                                       |
|------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `OTTERDOG_CONFIG_ROOT` | directory in which otterdog looks for `otterdog.jsonnet` or `otterdog.json` when no file is given with `--config`, and base directory of the `config_dir`; defaults to the current directory |
| `OTTERDOG_WEB_TIMEOUT` | timeout in milliseconds to load a page of the GitHub web interface or to wait for one of its elements, defaults to `10000`; increase it on a slow connection                                   |
| `VAULT_ADDR`           | address of the Vault when `vault_addr` is not set, see [HashiCorp Vault](#hashicorp-vault)                                                                                                       |
| `VAULT_TOKEN`          | token to access the Vault when `vault_token` is not set, see [HashiCorp Vault](#hashicorp-vault)                                                                                                 |
| `VAULT_USERNAME`       | username used to log in to the Vault interactively, asked for if not set                                                                                                                         |

The names of the environment variables that contain the credentials of an organization are defined in the
configuration, see [Environment based credentials](#environment-based-credentials).
