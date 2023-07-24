Otterdog requires Python 3.10+ to run.

## System requirements

A few system dependencies are required to be installed:

### Mandatory system dependencies

* [`python 3.10+`](https://www.python.org/): Python 3 + pip

```bash
apt install python3 python3-pip
```

* [`poetry`](https://python-poetry.org/): Python package manager

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

* [`go`](https://go.dev/): Go language compiler, v1.13+, needed for installing jsonnet-bundler

```bash
apt install golang
```

* [`jsonnet-bundler`](https://github.com/jsonnet-bundler/jsonnet-bundler): Package manager for jsonnet

```bash
go install -a github.com/jsonnet-bundler/jsonnet-bundler/cmd/jb@v0.5.1
```

### Optional system dependencies

Depending on the type of credential system you are using, install one of the following tools:

* [`bitwarden cli`](https://github.com/bitwarden/clients): command line tools to access a bitwarden vault.

```bash
snap install bw
```

* [`password manager`](https://www.passwordstore.org/): lightweight directory-based password manager.

```bash
apt install pass
```

## Build instructions

After installing the required system dependencies, a virtual python environment needs to be setup 
and populated with all python dependencies:

```console
$ make init
```

You should be set to finally run otterdog:

```console
$ ./otterdog.sh --version
```

Additionally, `make init` creates a symlink called `otterdog` in `~/.local/bin`, so you can also run it like that: 

```console
$ otterdog --version
```

## Shell integration

To enable shell completion, add the following snippet to your shell configuration file (`~/.bashrc` or `~/.zshrc`):

=== "bash"
    ``` shell
    eval "$(_OTTERDOG_COMPLETE=bash_source otterdog)"
    ```

=== "zsh"
    ``` shell
    eval "$(_OTTERDOG_COMPLETE=zsh_source otterdog)"
    ```

When running `otterdog` in a directory that contains a `otterdog.json` file, shell completion will be able to suggest 
organizations found in the `otterdog.json` file.