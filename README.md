<h1 align="center">

<a href="https://otterdog.eclipse.org">
  <img style="width: 350px;" src="https://github.com/eclipse-csi/.github/blob/main/artwork/eclipse-otterdog/Logo%20Color%20-%20Transparent%20Bg.png">
</a>

</h1>

<p align="center">
  <a href="https://pypi.org/project/otterdog"><img alt="PyPI" src="https://img.shields.io/pypi/v/otterdog.svg?color=blue&maxAge=86400" /></a>
  <a href="https://pypi.org/project/otterdog"><img alt="PyPI - Python Versions" src="https://img.shields.io/pypi/pyversions/otterdog.svg?maxAge=86400" /></a>
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
* go (mandatory): install using `apt install golang-1.23` or `snap install go`
* otterdog (mandatory): install using `pipx install otterdog`
* bitwarden cli tool (optional): install using `snap install bw`
* pass cli tool (optional): install using `apt install pass`

[Otterdog Presentation @ Open Source Summit 2023](https://docs.google.com/presentation/d/1lLqbhDQf9s5U2A2TkcoFYA39qtODcSot2308vnKbkbA/edit?usp=sharing)

[Default Configuration used @ Eclipse Foundation](https://github.com/EclipseFdn/otterdog-defaults/)

## Documentation

The documentation is available at [otterdog.readthedocs.io](https://otterdog.readthedocs.io).

## Build instructions

### System requirements:

* python3.10+ (mandatory): e.g. install using `apt install python3` or `pyenv`
* git (mandatory): install using `apt install git`
* go (mandatory): install using `apt install golang-1.23` or `snap install go`
* poetry (mandatory): install using `curl -sSL https://install.python-poetry.org | python3 -` or `pipx install poetry`
* bitwarden cli tool (optional): install using `snap install bw`
* pass cli tool (optional): install using `apt install pass`

### Building Steps

* Create a virtual python environment and install necessary python dependencies using poetry:

```console
$ make init
```

* Testing build

```console
$ ./otterdog.sh -h
```

## Setup

The general configuration for supported organizations and their corresponding credentials in order
to access their GitHub settings has to be placed in a json file (default: __otterdog.json__, can be changed
with the __-c__ flag), e.g.:

```json
{
  "organizations": [
    {
      "name": "<org name>",
      "github_id": "<github org id>",
      "credentials": {
        "provider": "<bitwarden | pass>",
        "item_id" : "39adacc9-2b51-41a9-a27e-ac7c00eea6a5"
      }
    }
  ]
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
* delete_repo

The credentials can be stored in different providers (bitwarden, pass).

### Bitwarden

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

### Pass

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
