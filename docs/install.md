Otterdog requires Python 3.11+ to run.

## Otterdog tool (command line interface)
### System requirements

A few system dependencies are required to be installed:

#### Mandatory system dependencies

* [`python 3.11+`](https://www.python.org/): Python 3 + pip + pipx

```bash
apt install python3 python3-pip pipx
```

* [`poetry`](https://python-poetry.org/): Python package manager

```bash
pipx install poetry>=2.0.1
```

* [`git`](https://git-scm.com/): popular distributed version control system

```bash
apt install git
```

#### Optional system dependencies

Depending on the type of credential system you are using, install one of the following tools:

* [`bitwarden cli`](https://github.com/bitwarden/clients): command line tools to access a bitwarden vault.

```bash
snap install bw
```

* [`password manager`](https://www.passwordstore.org/): lightweight directory-based password manager.

```bash
apt install pass
```

### Build instructions

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

### Shell integration

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


## Otterdog WebApp

Otterdog WebApp is available as a container image, with releases published to the [GitHub Container Registry (GHCR)](https://github.com/eclipse-csi/otterdog/pkgs/container/otterdog).

For Kubernetes environments, we also provide Helm charts to simplify deployment and configuration.

This guide covers how to deploy the Otterdog WebApp using **Helm charts**.

### System Requirements

Make sure the following requirements are met before deployment:

- A running Kubernetes cluster
- [Helm](https://helm.sh) installed


### GitHub requirements

#### Create a GitHub App

<!--github-app-start-->

It is required if you are the integration with GitHub ([Create a GitHub app](https://docs.github.com/en/organizations/managing-programmatic-access-to-your-organization/adding-and-removing-github-app-managers-in-your-organization#giving-someone-the-ability-to-manage-all-github-apps-owned-by-the-organization))

1. Go to your organization `https://github.com/organizations/<ORG>`
2. Click Settings.
3. In the left sidebar, select <> Developer settings
4. Click GitHub Apps
5. New GitHub App

**Basic Information**

- Add GitHub App name: `<choose a name>`
- Homepage URL: `<OTTERDOG-WEBAPP>`

**Webhook**

- [X] Active
- Webhook url: `<OTTERDOG-WEBAPP>`
- Secret: Choose the secret

Add the following permissions and events:


Repository Permissions

| Permission           | Access Level |
|----------------------|--------------|
| Actions              | Read & Write |
| Administration       | Read & Write |
| Commit statuses      | Read & Write |
| Contents             | Read & Write |
| Environments         | Read & Write |
| Issues               | Read only    |
| Metadata             | Read only    |
| Pages                | Read & Write |
| Pull requests        | Read & Write |
| Secrets              | Read & Write |
| Variables            | Read & Write |
| Webhooks             | Read & Write |
| Workflows            | Read & Write |

Organization Permissions

| Permission                  | Access Level |
|-----------------------------|--------------|
| Administration              | Read & Write |
| Custom Organization Roles   | Read & Write |
| Members                     | Read only    |
| Plan                        | Read only    |
| Secrets                     | Read & Write |
| Variables                   | Read & Write |
| Webhooks                    | Read & Write |

Events

| Event                   |
|-------------------------|
| Issue comment           |
| Pull request            |
| Pull request review     |
| Push                    |
| Workflow job            |
| Workflow run            |

<!--github-app-end-->

### Deployment Steps

#### Step 1: Add the Helm Repository

```bash
helm repo add eclipse-csi https://eclipse-csi.github.io/helm-charts
helm repo update
```

#### Step 2: Prepare Configuration

Create a `values.yaml` file to define your deployment configuration:

This is an example

```yaml
valkey:
  auth:
    enabled: false

mongodb:
  auth:
    enabled: true
    rootPassword: <DEFINE MONGODB PASSWORD>

ghproxy:
  redisAddress: otterdog-valkey-primary.default.svc.cluster.local:6379

config:
  configOwner: "<ORGANIZATION>"
  configToken: "<GITHUB TOKEN (BASE64)>"
  configRepo: "otterdog-configs"
  configPath: "otterdog.json"
  mongoUri: "mongodb://root:secret@otterdog-mongodb.default.svc.cluster.local:27017/otterdog"
  redisUri: "redis://otterdog-valkey-primary.default.svc.cluster.local:6379"
  ghProxyUri: "http://otterdog-ghproxy.default.svc.cluster.local:8888"
  dependencyTrackUrl: "https://otterdog-dt.default.svc.cluster"
  dependencyTrackToken: "faketoken"

github:
  webhookSecret: "<WEBHOOK SECRET (BASE64)>"
  appId: "<GITHUB APP ID>"
  appPrivateKey: "<GITHUB APP PRIVATE KEY (BASE64)>"
  webhookValidationContext: "otterdog/otterdog-validation"
  webhookSyncContext: "otterdog/otterdog-sync"

```

#### Step 3: Install Otterdog WebApp

```bash
helm install eclipse-csi otterdog -f values.yaml
```

### Step 4: Verify the Deployment

Use the following commands to verify that the WebApp is running:

```bash
kubectl get pods
kubectl get svc
kubectl get ingress
```


### Updating the Deployment

To upgrade to the latest chart or image version:

```bash
helm repo update
helm upgrade eclipse-csi otterdog -f values.yaml
```

### Uninstalling Otterdog

To remove the WebApp from your cluster:

```bash
helm uninstall otterdog
```

### Additional Resources

- [Otterdog GitHub Repository](https://github.com/eclipse-csi/otterdog)
- [Otterdog Container Images (GHCR)](https://github.com/eclipse-csi/otterdog/pkgs/container/otterdog)
- [Helm Documentation](https://helm.sh/docs/)
- [GitHub Container Registry Docs](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
