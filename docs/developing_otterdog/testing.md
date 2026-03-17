# Testing

This document describes how to run tests for Otterdog. You should setup your development environment as described in the [Development Setup](development_setup.md) guide before running tests.

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
            "provider": "bitwarden",
            "item_id" : "<item ide>"

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

Make sure you have the eclipse-csi helm chart repository

```bash
helm repo add eclipse-csi https://eclipse-csi.github.io/helm-charts
```

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
    include-markdown "../operating_otterdog/install.md"
    start="<!--github-app-start-->"
    end="<!--github-app-end-->"
%}


#### Configure the `values.yaml` to setup your otterdog webapp

```yaml
config:
  configOwner: "otterdog-<github username>"  # GitHub organization hosting the otterdog.json
  configToken: ""  #  A base64 valid GitHub token, no need for any permissions, just for rate limit purposes
  dependencyTrackToken: ""  # A base64 depednecy track generated

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

Make sure you have the eclipse-csi, tailscale and dependency-track helm chart repositories added

```bash
helm repo add dependency-track https://dependencytrack.github.io/helm-charts
helm repo add eclipse-csi https://eclipse-csi.github.io/helm-charts
helm repo add tailscale https://pkgs.tailscale.com/helmcharts
```

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
