<h1 align="center">

<a href="https://otterdog.eclipse.org">
  <img style="width: 350px;" src="https://raw.githubusercontent.com/eclipse-csi/.github/refs/heads/main/artwork/eclipse-otterdog/Logo%20Color%20-%20Transparent%20Bg.png">
</a>

</h1>

<p align="center">
  <a href="https://pypi.org/project/otterdog"><img alt="PyPI" src="https://img.shields.io/pypi/v/otterdog.svg?color=blue&maxAge=600" /></a>
  <a href="https://pypi.org/project/otterdog"><img alt="PyPI - Python Versions" src="https://img.shields.io/pypi/pyversions/otterdog.svg?maxAge=600" /></a>
  <a href="https://github.com/eclipse-csi/otterdog/blob/main/LICENSE"><img alt="EPLv2 License" src="https://img.shields.io/github/license/eclipse-csi/otterdog" /></a>
  <a href="https://github.com/eclipse-csi/otterdog/actions/workflows/build.yml?query=branch%3Amain"><img alt="Build Status on GitHub" src="https://github.com/eclipse-csi/otterdog/actions/workflows/build.yml/badge.svg?branch:main&workflow:Build" /></a>
  <a href="https://otterdog.readthedocs.io"><img alt="Documentation Status" src="https://readthedocs.org/projects/otterdog/badge/?version=latest" /></a><br>
  <a href="https://scorecard.dev/viewer/?uri=github.com/eclipse-csi/otterdog"><img alt="OpenSSF Scorecard" src="https://api.securityscorecards.dev/projects/github.com/eclipse-csi/otterdog/badge" /></a>
  <a href="https://www.bestpractices.dev/projects/9624"><img alt="OpenSSF Best Practices" src="https://www.bestpractices.dev/projects/9624/badge" /></a>
  <a href="https://slsa.dev"><img alt="OpenSSF SLSA Level 3" src="https://slsa.dev/images/gh-badge-level3.svg" /></a>
</p>

# Eclipse Otterdog

## Introduction

Otterdog is a tool to manage GitHub organizations at scale using a configuration as code approach.
It is actively developed by the Eclipse Foundation and used to manage its numerous projects hosted on GitHub.

## Quickstart

To install and use the cli part of otterdog you have to install the following:

* git (mandatory): install using `apt install git`
* otterdog (mandatory): install using `pipx install otterdog`
* bitwarden cli tool (optional): install using `snap install bw`
* pass cli tool (optional): install using `apt install pass`

[Otterdog Presentation @ Open Source Summit 2023](https://docs.google.com/presentation/d/1lLqbhDQf9s5U2A2TkcoFYA39qtODcSot2308vnKbkbA/edit?usp=sharing)

[Default Configuration used @ Eclipse Foundation](https://github.com/EclipseFdn/otterdog-defaults/)

## Documentation

The documentation is available at [otterdog.readthedocs.io](https://otterdog.readthedocs.io).

## Build instructions

### System requirements:

* python3.11+ (mandatory): e.g. install using `apt install python3` or use `pyenv install 3.12`
* git (mandatory): install using `apt install git`
* poetry (mandatory): install using `pipx install poetry`
* dynamic versioning plugin (mandatory): install using `pipx inject poetry "poetry-dynamic-versioning[plugin]"`
* bitwarden cli tool (optional): install using `snap install bw`
* pass cli tool (optional): install using `apt install pass`

### Building Steps

* Create a virtual python environment and install necessary python dependencies using poetry:

```console
$ make init
```

Running `make init` will also install `poetry` and the `dynamic versioning plugin` if it is not installed yet.

* Testing build

```console
$ ./otterdog.sh -h
```

## Quick Setup

To start using the cli part of `otterdog` right away on a specific organization you have to set up the following:

- define a default configuration to use, you can use the following [default config](https://github.com/eclipse-csi/otterdog/blob/main/examples/template/otterdog-defaults.libsonnet) as a starting point
- create a `otterdog.json` file that contains the list of organizations you want to manage and some customizations
- start managing your organizations using the cli

### Default configuration

You can define your own default configuration or use the following base template right away: `https://github.com/eclipse-csi/otterdog#examples/template/otterdog-defaults.libsonnet@main`.

### Otterdog configuration

Create a `otterdog.json` file with the following content (replace bracketed values according to your setup):

```json
{
  "defaults": {
    "jsonnet": {
      "base_template": "https://github.com/eclipse-csi/otterdog#examples/template/otterdog-defaults.libsonnet@main",
      "config_dir": "orgs"
    },
    "github": {
      "config_repo": ".otterdog"
    }
  },
  "organizations": [
    {
      "name": "<project-name>",
      "github_id": "<github-id>",
      "credentials": {
        "provider": "bitwarden",
        "item_id": "<bitwarden item id>"
      }
    }
  ]
}
```

The name of the configuration file can be freely chosen (can be specified with the __-c__ flag).
However, when named `otterdog.json`, the cli tool will automatically detect and use that file if it is in the current working directory.

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
        "2fa_seed": "<path/to/2fa_seed>"
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

## Typical Workflow

In general, all operations act on the local configuration stored in `<cwd>/<config-dir>/<organization>/<organization>.jsonnet`.

A typical workflow to handle changes to an organization are as follows:

1. (first time) run an initial `import` of the organization
2. (first time) run an `apply` operation to create all resources already inherited from the default config (e.g. config repo)
3. (regular) fetch the latest config from the config repo using `fetch-config`
4. (optional) make any local changes to the configuration
5. (optional) run the `validate` operation to see if the configuration is syntactically and semantically correct
6. (optional) run the `plan` operation to see which changes would be applied taking the current live configuration into account
7. (regular) run the `apply` operation to actually apply the changes (also runs `validate` and `plan`, so steps 6 & 7 are redundant)
8. (regular) push the local configuration to the config repo using the `push-config` operation
