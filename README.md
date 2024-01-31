[![Build](https://github.com/eclipse-csi/otterdog/actions/workflows/build.yml/badge.svg)](https://github.com/eclipse-csi/otterdog/actions/workflows/build.yml)
[![Documentation status](https://readthedocs.org/projects/otterdog/badge/?version=latest)](https://otterdog.readthedocs.io/en/latest/?badge=latest)
[![PyPI](https://img.shields.io/pypi/v/otterdog?color=blue)](https://pypi.org/project/otterdog)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/otterdog)](https://pypi.org/project/otterdog)
[![EPLv2 License](https://img.shields.io/github/license/eclipse-csi/otterdog)](https://github.com/eclipse-csi/otterdog/blob/main/LICENSE)

# Otterdog

## Introduction

Otterdog is a tool to manage GitHub organizations at scale using a configuration as code approach.
It is actively developed by the Eclipse Foundation and used to manage its numerous projects hosted on GitHub.

## Quickstart

[Otterdog Presentation @ Open Source Summit 2023](https://docs.google.com/presentation/d/1lLqbhDQf9s5U2A2TkcoFYA39qtODcSot2308vnKbkbA/edit?usp=sharing)

[Default Configuration used @ Eclipse Foundation](https://github.com/EclipseFdn/otterdog-defaults/)

## Documentation

The documentation is available at [otterdog.readthedocs.io](https://otterdog.readthedocs.io).

## Build instructions

### System requirements:

* python3.10 (mandatory): install using `apt install python3`
* poetry (mandatory): install using `curl -sSL https://install.python-poetry.org | python3 -` or `pipx install poetry`
* go (mandatory for installing jsonnet-bundler): install using `apt install golang`
* jsonnet-bundler (mandatory): install using `go install -a github.com/jsonnet-bundler/jsonnet-bundler/cmd/jb@v0.5.1`
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
* delete_repo

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

# Container Runtime (Linux/MacOS)

## Requirements
* An otterdog.json already in your current directory
* (Recommended) a directory orgs


## Building Container Image
* Creating a container local image
```console
make container_build
```
## Building a Development Container Image
* Creating a container development local image
```console
make container_build_dev
```

## Running otterdog in a container

### Using Bitwarden client
* Firstly you need to login and unlock your Bitwarden session by executing the command below
```console
bw login
bw unlock
```
* As result, you will get a token session. Please follow example below to make available in your terminal (Linux/MacOS)
```console
export BW_SESSION="ffdsajklloremipsumfxs000f000r0loremipsum"
```

### Using pass client
* Pass needs to be already installed as well as configured with all data needed in [otterdog.json](./otterdog.json) by executing ```pass``` in your profile

### Activating Otterdog Container Runtime
* Activate otterdog environment will create an alias ```otterdog```
```console
source scripts/bin/active-otterdog
```
* Checking otterdog alias
```console
otterdog -h
```
* Deactivating otterdog environment
```console
deactivate-otterdog
```

### otterdog container Arguments

* An table arguments

| Argument                     | Description                                                                           |
|------------------------------|---------------------------------------------------------------------------------------|
| -g                           | .gnupg directory PATH by default $HOME/.gnupg if it is not provided                   |
| -o                           | Output ORGS directory path by default $PWD/orgs if it is not provided                 |
| -c                           | otterdog json file path by default $PWD/otterdog.json if it is not provided           |
| -p                           | .password-store directory PATH by default $HOME/.password-store if it is not provided |
| -h                           | Help about container arguments and otterdog                                           |

* Please find below an example to show configuration
```console
otterdog -c $PWD/otterdog.json -g $HOME/.gnupg -o $PWD/orgs apply -f
```


### Usage Otterdog Container Runtime
* Please follow the section [Usage](#usage)
* Please bear in mind that all command need to drop **.sh**

### Activating Development Otterdog Container Runtime
* Activating development otterdog environment will run eclipse/otterdog:dev. Thus it can be used container shell. Please find below an example
```console
export OTTERDOG_DEV=1; source scripts/bin/active-otterdog
otterdog /bin/bash
```
* To activate development otterdog environment with argument
```console
export OTTERDOG_DEV=1; source scripts/bin/active-otterdog
otterdog -c $PWD/otterdog.json -g $HOME/.gnupg -o $PWD/orgs /bin/bash
```

* Checking otterdog environment
```console
/app/otterdog.sh -h
```
* Deactivating development otterdog runtime type ```exit``` then ```deactivate-otterdog```

### Usage Development Otterdog Container Runtime
* Please follow the section [Usage](#usage)

## Cleaning container environment
* Please use the macro below
```console
make container_clean
```

## Known issues
