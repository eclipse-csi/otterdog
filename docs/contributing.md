We'd love you to contribute to Otterdog!

## Eclipse Contributor Agreement (ECA)

Log into the [Eclipse projects forge](https://www.eclipse.org/contribute/cla) (you will need to create
an account with the Eclipse Foundation if you have not already done so); click on "Eclipse Contributor
Agreement"; and Complete the form. Be sure to use the same email address when you register for the
account that you intend to use on Git commit records.

[More about ECA FAQ](https://www.eclipse.org/legal/eca/)


## Issues

Questions, feature requests and bug reports are all welcome as
[discussions](https://github.com/eclipse-csi/otterdog/discussions) or
[issues](https://github.com/eclipse-csi/otterdog/issues).

## Pull Requests

It should be extremely simple to get started and create a Pull Request.

Unless your change is trivial (typo, docs tweak etc.), please create an issue to discuss the change before
creating a pull request.

If you're looking for something to get your teeth into, check out the
["help wanted"](https://github.com/eclipse-csi/otterdog/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22help%20wanted%22)
label on GitHub.

To make contributing as easy and fast as possible, you'll want to run tests and linting locally. Luckily,
Otterdog has few dependencies, doesn't require compiling and tests don't need access to databases, etc.
Because of this, setting up and running the tests should be very simple.

## Prerequisites

You'll need the following prerequisites:

### Basic pre-requesite tools

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

### [Optional] Otterdog WebApp development prerequisities

- Docker Engine (including Docker Compose)
- Minikube
- Skaffold

Why Docker?

Docker simplifies development environment set up.

Install [Docker Engine](https://docs.docker.com/engine/installation/)

Why Minikube?

Minikube will provide a local kubernetes cluster and using Otterdog from helm charts

Install [Minikkube](https://minikube.sigs.k8s.io/docs/start/)

Why Skaffold?

Skaffold will build, deploy and watch your development environment, including the infrastructure services
redis, mongodb and ghproxy.

Install [Skaffold](https://skaffold.dev/docs/install/)

## Getting the source code

#### Fork the repository
[Fork](https://docs.github.com/en/get-started/quickstart/fork-a-repo) the [repository](https://github.com/eclipse-csi/otterdog.git)
on GitHub and clone your fork locally.

```bash
git clone https://github.com/<your username>/otterdog.git
cd otterdog
```

#### Add a git remote

Add a [remote](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/configuring-a-remote-for-a-fork)
and regularly [sync](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/syncing-a-fork)
to make sure you stay up-to-date with our repository:

```bash
git remote add upstream https://github.com/eclipse-csi/otterdog
git checkout main
git fetch upstream
git merge upstream/main
```

#### Prepare development environment

Install otterdog development Python dependencies
```bash
make init
```

### Pre-commit hooks

The project extensively uses `pre-commit` hooks to ensure consistent source code formatting and type checking.
To enable `pre-commit` run the following:

```bash
poetry run pre-commit install
```

### Check out a new branch and make your changes

Create a new branch for your changes.

```bash
# Checkout a new branch and make your changes
git checkout -b my-new-feature-branch
# Make your changes...
```

### Run tests

Run tests locally to make sure everything is working as expected.

```bash
# Run tests
make test
```

Note: Code coverage HTML is also available in `htmlcov/`

### Commit and push your changes

Commit your changes, push your branch to GitHub, and create a pull request.

Please follow the pull request template and fill in as much information as possible. Link to any relevant issues and include a description of your changes.

When your pull request is ready for review, add a comment with the message "please review" and we'll take a look as soon as we can.

## Development Resources

### [Optional] Creating an Organization for development
On your profile, [create one orgnaization](https://github.com/account/organizations/new?plan=free)

* **Organization name**: `otterdog-<github username>` (Ex: otterdog-foobar)
* **Contact email**: <your@email>
* **This organization belongs to**: My personal account

Accept the Terms of Service (if you agree)

#### Configure your otterdog (source code) to work with your development organization

https://otterdog.readthedocs.io/en/latest/setup/#otterdog-configuration

```json
{
    "defaults": {
        "jsonnet": {
        "base_template": "https://github.com/<Github Username>/otterdog#examples/template/otterdog-defaults.libsonnet@main",
        "config_dir": "orgs"
        }
    },
    "organizations": [
        {
        "name": "otterdog-<Github Username>",
        "github_id": "otterdog-<Github Username>",
        "credentials": {
            "provider": "plain",
            "api_token": "ghp_<TOKEN>",
            "username": "<Github Username>",
            "password": "<Password>",
            "twofa_seed": "<2FA TOTP seed>"
        }
        }
    ]
}
```

##### [Optional] Setup common Otterdog configuration repository

This will store and maintain the `otterdog.json` in the repository.

Go to your organization `https://github.com/otterdog-<github username>` > Repositories > New repository

- Repository name *: .otterdog

Click on Create repository

Edit your current and include:

```json
    "github": {
      "config_repo": ".otterdog"
    },
```


### [Optional] Otterdog WebApp development environment

To run the otterdog webapp (without integration with GitHub)

```bash
make dev-webapp
```

If you want use the integration with GitHub, you can use the tailscale

#### Setup a tailscale to enable GitHub Webhooks to your development environment

1. Sign up/Login to tail [tailscale](https://tailscale.com)

2. Go to tailscale admin console https://login.tailscale.com/admin/machines

We use [tailscale on Kubernetes](https://tailscale.com/learn/managing-access-to-kubernetes-with-tailscale#preparing-the-operator) (minikube), configuring it:

1. Go to tailscale admin console -> ACL (https://login.tailscale.com/admin/acls/file)

    Include or update the `tagOwners`

    ```json
        "tagOwners": {
            "tag:k8s-operator": [],
            "tag:k8s":          ["tag:k8s-operator"],
        },
    ```

    Add ``tag:k8s`` to the ``nodeAttrs``:

    ```json
	"nodeAttrs": [
		{

			"target": ["autogroup:member", "tag:k8s"],
			"attr":   ["funnel"],
		},
		{
			"target": ["tag:k8s"], // tag that Tailscale Operator uses to tag proxies; defaults to 'tag:k8s'
			"attr":   ["funnel"],
		},
	],
    ```

2. Create an OAuth in Settings > OAuth clients (https://login.tailscale.com/admin/settings/oauth)

    Create an OAuth client in the OAuth clients page of the admin console. Create the client with **Devices Core** and **Auth Keys**
    write scopes, and the tag `tag:k8s-operator`.

    This is well described in the [official doc](https://tailscale.com/kb/1236/kubernetes-operator#prerequisites)

    Your new OAuth client's Client ID and Client Secret will be displayed—copy these values now as you'll need them in the next step.


3. Save your tailscale DNS (https://login.tailscale.com/admin/dns)

    It might look like `tail<some hash>.ts.net`

4. Export them on you terminal

    ```bash
    export TS_CLIENT_ID=<client id>
    export TS_CLIENT_SECRET=<client secret>
    export TS_DNS=tail<some hash>.ts.net
    ```

    NOTE: If you close terminal, you will need re-export

#### Create a GitHub App

**NOTES**:

 - Replace `<OTTERDOG-WEBAPP>` by your `tail<some hash>.ts.net`
 - You can always double check the URL at https://login.tailscale.com/admin/machines as multiple instances
 of your development environment can generate `otterdog-1`, `otterdog-2` ...

{%
    include-markdown "./install.md"
    start="<!--github-app-start-->"
    end="<!--github-app-end-->"
%}


#### Configure the `values.yaml` to setup your otterdog webapp

```yaml
config:
  configOwner: "otterdog-<github username>"  # GitHub organization hosting the otterdog.json
  configToken: ""  #  A base64 valid GitHub token, no need for any permissions, just for rate limit purposes
  dependecyTrackToken: ""  # A base64 depednecy track generated

github:
  webhookSecret: ""  # The Base64 webhook secret as configured for the GitHub App
  appId: ""  # The APP id created in GitHub
  appPrivateKey: ""  # The base64 App Private Key
```

NOTE:

In the dev configuration the otterdog webapp uses the following repositories:

```json
config:
  configRepo: "otterdog-configs"
  configPath: "otterdog.json"
```

You can overwrite it on `values.yaml`

It is recommeded to create the repository `otterdog-configs` and add the `otterdog.json`

Example of `otterdog.json`

```json
{
    "defaults": {
        "jsonnet": {
            "base_template": "https://github.com/<GitHub Username>/otterdog#examples/template/otterdog-defaults.libsonnet@main",
            "config_dir": "orgs"
        }
    },
    "github": {
        "config_repo": ".otterdog"
    },
    "organizations": [
        {
            "name": "otterdog-<GitHub Username>",
            "github_id": "otterdog-<GitHub Username>"
        }
    ]
}
```

#### Run otterdog with tailscale

Initiate otterdog webapp with tailscale

```bash
make dev-webapp-tunnel
```

You can see at https://login.tailscale.com/admin/machines the otterdog machine.

Otterdog WebApp is reacheable at https://otterdog.tail<some hash>.ts.net

Init the otterdog and watch the logs

```bash
curl  https://otterdog.tail<hash>.ts.net/internal/init
```
Dependency Track is reacheable at https://sbom.tail<some hash>.ts.net (it still need to be re-configured, see it below)

#### [Optional] Configure dependency track

1. Access the https://sbom.tail<some hash>.ts.net ([default DependencyTrack credentials](https://docs.dependencytrack.org/getting-started/initial-startup/))
   (First time will ask to change password and re-login)

2. To generate the `dependencyTrackToken` go to `Administration` > `Access Management`> `Teams`

3. Create a Team or choose one (i.e. `Automation`) create and API Key.

4. Use this API Key in `depdencyTrackToken` on `values.yaml`

It will reloadd automatically.

## Code style and requirements

TODO

## Documentation style

Documentation is written in Markdown and built using [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/).

### Code documentation

When contributing to otterdog, please make sure that all code is well documented. The following should be documented using properly formatted docstrings:

- Modules
- Class definitions
- Function definitions
- Module-level variables

Otterdog uses [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) formatted according to [PEP 257](https://www.python.org/dev/peps/pep-0257/) guidelines. (See [Example Google Style Python Docstrings](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html) for further examples.)

Where this is a conflict between Google-style docstrings and pydocstyle linting, follow the pydocstyle linting hints.

Class attributes and function arguments should be documented in the format "name: description." When applicable, a return type should be documented with just a description. Types are inferred from the signature.

```python
class Foo:
    """A class docstring.

    Attributes:
        bar: A description of bar. Defaults to "bar".
    """

    bar: str = 'bar'
```

```python
def bar(self, baz: int) -> str:
    """A function docstring.

    Args:
        baz: A description of `baz`.

    Returns:
        A description of the return value.
    """

    return 'bar'
```

You may include example code in docstrings. This code should be complete, self-contained, and runnable. Docstring examples are tested using [doctest](https://docs.python.org/3/library/doctest.html), so make sure they are correct and complete.

!!! note "Class and instance attributes"
    Class attributes should be documented in the class docstring.

    Instance attributes should be documented as "Args" in the `__init__` docstring.
