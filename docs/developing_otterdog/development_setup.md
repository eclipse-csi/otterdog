# Development Setup

This document describes how to set up a development environment for Otterdog.

## Basic prerequisite tools

- Any Python version **>= 3.11**
- **git**
- **make**
- [**poetry >= 2**](https://python-poetry.org/docs/#installation)

Verify that you have Make installed
We use Make to run, build, update docs, tests, formatting, etc. Verify that you have Make installed in your environment.

```bash
make --version
```
If you do not have Make installed, consult your operating system documentation on how to install make.

Install poetry (preferred using pipx)

```bash
pipx install poetry
```

or alternatively

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

## [Optional] Otterdog WebApp development prerequisites

- Docker Engine (including Docker Compose)
- Minikube
- Helm
- Skaffold

Why Docker?

Docker simplifies development environment set up.

Install [Docker Engine](https://docs.docker.com/engine/installation/)

Why Minikube?

Minikube will provide a local kubernetes cluster and using Otterdog from helm charts

Install [Minikkube](https://minikube.sigs.k8s.io/docs/start/)

Why helm?

Helm will deploy otterdog, dependency-track and ghproxy in the minikube cluster.

Install [Helm](https://helm.sh/docs/intro/install/)

Why Skaffold?

Skaffold will build, deploy and watch your development environment, including the infrastructure services
redis, mongodb and ghproxy.

Install [Skaffold](https://skaffold.dev/docs/install/)
