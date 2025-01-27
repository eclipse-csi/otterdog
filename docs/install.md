Otterdog requires Python 3.11+ to run.

## System requirements

A few system dependencies are required to be installed:

### Mandatory system dependencies

* [`python 3.11+`](https://www.python.org/): Python 3 + pip

```bash
apt install python3 python3-pip
```

* [`poetry`](https://python-poetry.org/): Python package manager

```bash
pipx install poetry>=2.0.1
```

* [`git`](https://git-scm.com/): popular distributed version control system

```bash
apt install git
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
