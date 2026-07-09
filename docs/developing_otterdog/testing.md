# Testing

This document describes how to run tests for Otterdog. You should set up your development environment as described in the [Development Setup](development_setup.md) guide before running tests.

## Prerequisites

* [Skaffold](https://skaffold.dev/docs/install/)
* [tailscale](https://tailscale.com/download)
* [minikube](https://minikube.sigs.k8s.io/docs/start/?arch=%2Flinux%2Fx86-64%2Fstable%2Fbinary+download)
* [k9s](https://k9scli.io/topics/install/)

## Development Resources

### [Optional] Creating an Organization for development

On your profile, [create an organization](https://github.com/account/organizations/new?plan=free)

* **Organization name**: `otterdog-<github username>` (Ex: otterdog-foobar)
* **Contact email**: <your@email>
* **This organization belongs to**: My personal account

Accept the Terms of Service (if you agree)

#### Fork otterdog

Fork otterdog in your own organization. This will act as a base for modifications and contributions to the project, and will serve as the URL for the otterdog config `base_template`.

```
https://github.com/<Github Username>/otterdog
```

#### Create a user token

Create a [Personal Access Token](https://github.com/settings/tokens) with sufficient permissions to access the organization API.

The GitHub API token needs to have the following scopes enabled: `repo`, `workflow`, `admin:org`, `admin:org_hook`, `delete_repo`.

For more about credentials, see: https://otterdog.readthedocs.io/en/latest/operating_otterdog/setup/#credentials

### Credentials provider configuration

For the purpose of this testing section, we use GitHub environment variables, but third-party providers are also supported, such as `pass` or `bitwarden`.

Add these environment variables at the GitHub org level: https://github.com/organizations/otterdog-<Github Username>/settings/secrets/actions/new:
* `OTTER_USERNAME`
* `OTTER_PASSWORD`
* `OTTER_TOTP_SEED`
* `OTTER_API_TOKEN` (token previously created)

> **NOTE:** 2FA must be activated on your account.

For other credential providers, see: https://otterdog.readthedocs.io/en/latest/operating_otterdog/setup/#credentials

#### Configure your otterdog (source code) to work with your development organization

Create a new repository named `otterdog-config` and set up the otterdog configuration: [otterdog-configuration](https://otterdog.readthedocs.io/en/latest/operating_otterdog/setup/#otterdog-configuration)

Go to your organization `https://github.com/otterdog-<github username>` > Repositories > New repository

- Repository name: `otterdog-config`

Click on **Create repository**.

Then create the file `otterdog.json` in this repository with all the required settings.

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
                "provider": "env",
                "api_token": "OTTER_API_TOKEN",
                "username": "OTTER_USERNAME",
                "password": "OTTER_PASSWORD",
                "twofa_seed": "OTTER_TOTP_SEED"
            }
        }
    ]
}
```

##### [Optional] Set up Otterdog GitHub org configuration repository


Go to your organization `https://github.com/otterdog-<github username>` > Repositories > New repository

- Repository name: `.otterdog`

Click on **Create repository**.

If the name differs from `.otterdog`, edit your configuration and include:

```json
    "github": {
      "config_repo": ".<your_otterdog_github_config_repo>"
    },
```


### [Optional] Otterdog WebApp development environment

To run the otterdog webapp (without integration with GitHub)

Make sure you have the `eclipse-csi` Helm chart repository added:

```bash
helm repo add eclipse-csi https://eclipse-csi.github.io/helm-charts
```

```bash
make dev-webapp
```

If you want use the integration with GitHub, you can use the tailscale

#### Setup a tailscale to enable GitHub Webhooks to your development environment

1. Sign up/Login to tail [tailscale](https://tailscale.com)

2. Go to tailscale [admin console](https://login.tailscale.com/admin/machines)

We use [tailscale on Kubernetes](https://tailscale.com/learn/managing-access-to-kubernetes-with-tailscale#preparing-the-operator) (minikube), configuring it:

1. Go to tailscale admin console -> [ACL](https://login.tailscale.com/admin/acls/file)

    Include or update the `tagOwners`

    ```json
        "tagOwners": {
            "tag:k8s-operator": [],
            "tag:k8s":          ["tag:k8s-operator"],
        },
    ```

    Add `tag:k8s` to the `nodeAttrs`:

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


3. Save your [tailscale DNS](https://login.tailscale.com/admin/dns)

    It might look like `tail<some hash>.ts.net`

4. Export them in your terminal

    ```bash
    export TS_CLIENT_ID=<client id>
    export TS_CLIENT_SECRET=<client secret>
    export TS_DNS=tail<some hash>.ts.net
    ```

    > **NOTE:** If you close the terminal, you will need to re-export these values.

5. Test secrets

```shell
export TS_ACCESS_TOKEN="$(
  curl -sS \
    -d "client_id=${TS_CLIENT_ID}" \
    -d "client_secret=${TS_CLIENT_SECRET}" \
    "https://api.tailscale.com/api/v2/oauth/token" \
  | jq -r '.access_token'
)"

echo "$TS_ACCESS_TOKEN"

curl -sS \
  -H "Authorization: Bearer ${TS_ACCESS_TOKEN}" \
  "https://api.tailscale.com/api/v2/tailnet/-/devices" \
| jq .

```

6. Enabling HTTPS

Official documentation: https://tailscale.com/docs/how-to/set-up-https-certificates

Go to the dns configuration page: https://login.tailscale.com/admin/dns

HTTPS Certificates -> Click `Enable HTTPS...`

#### Create a tailscale GitHub App

**NOTES**:

 - Replace `<OTTERDOG-WEBAPP>` by your `tail<some hash>.ts.net`
 - You can always double check the URL at https://login.tailscale.com/admin/machines as multiple instances
 of your development environment can generate `otterdog-1`, `otterdog-2` ...

{%
    include-markdown "../operating_otterdog/install.md"
    start="<!--github-app-start-->"
    end="<!--github-app-end-->"
%}

The otterdog app should appear in the organization settings > Third-party Access > GitHub Apps:
https://github.com/organizations/otterdog-<GitHub Username>/settings/apps

#### Install the GitHub App in the organization

Once the app is created, you need to install it in your organization:

https://github.com/organizations/otterdog-<GitHub Username>/settings/apps/otterdog-<GitHub Username>-org-app/installations

Click **Install** next to your organization and grant the required permissions.

#### Configure the `values.yaml` to setup your otterdog webapp

This file must be set at the root level of your otterdog fork project.

```yaml
config:
  configOwner: "otterdog-<github username>"  # GitHub organization hosting the otterdog.json
  configToken: ""  # A base64-encoded GitHub token — no specific permissions required, used only for rate-limiting
  dependencyTrackToken: ""  # A base64-encoded Dependency Track API token

github:
  webhookSecret: ""  # The base64-encoded webhook secret as configured for the GitHub App
  appId: ""  # The App ID created in GitHub
  appPrivateKey: ""  # The base64-encoded App private key (generate with: base64 -w 0 private.key)
```

> **IMPORTANT:** Do not forget to convert secrets in base64 when mentioned. When generating a base64 token from a string (e.g. a token or secret), use `echo -n` to avoid including a trailing newline in the encoded value:
> ```bash
> echo -n "your-token-or-secret" | base64
> ```

> **NOTE:** In the dev configuration, the Otterdog webapp uses the following repositories by default:

```yaml
config:
  configRepo: "otterdog-configs"
  configPath: "otterdog.json"
```

You can override these defaults in `values.yaml`

It is recommended to create the repository `otterdog-configs` and add the `otterdog.json` file.

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

Make sure you have the `eclipse-csi`, `tailscale`, and `dependency-track` Helm chart repositories added:

```bash
helm repo add dependency-track https://dependencytrack.github.io/helm-charts
helm repo add eclipse-csi https://eclipse-csi.github.io/helm-charts
helm repo add tailscale https://pkgs.tailscale.com/helmcharts
```

Start the otterdog webapp with the tailscale tunnel:

```bash
make dev-webapp-tunnel
```

You can verify the machine is registered at https://login.tailscale.com/admin/machines.

The Otterdog WebApp is reachable at `https://otterdog.tail<some hash>.ts.net`

Trigger the Otterdog initialization:

```bash
curl https://otterdog.tail<some hash>.ts.net/internal/init
```

Dependency Track is reachable at `https://sbom.tail<some hash>.ts.net` (it still needs to be configured — see below)

#### Verify webhook delivery

Once the service is running and the GitHub App is installed in your organization, verify that webhooks are correctly reaching the backend by sending a **ping** event from the app's advanced settings:

https://github.com/organizations/otterdog-<GitHub Username>/settings/apps/otterdog-<GitHub Username>-org-app/advanced

Click **Redeliver** on the most recent **ping** delivery to trigger a test event. Check the otterdog backend logs to confirm the ping was received:

```shell
[2026-07-01 09:30:22.093  ] [9] [INFO] ping (3d5b7472-7522-11f1-9353-7f66c710a3db)
```

#### [Optional] Configure dependency track

1. Access the https://sbom.tail<some hash>.ts.net ([default DependencyTrack credentials](https://docs.dependencytrack.org/getting-started/initial-startup/))
   (First time will ask to change password and re-login)

2. To generate the `dependencyTrackToken`, go to `Administration` > `Access Management` > `Teams`

3. Create a Team or choose one (i.e. `Automation`) create and API Key.

4. Use this API Key as `dependencyTrackToken` in `values.yaml`

It will reload automatically.


#### Test otterdog client

This section walks through basic end-to-end testing of the otterdog CLI against your development organization.

##### 1. Test GitHub web access

Export your credentials and set the path to your local otterdog configuration project, then verify that web-based login works:

```shell
export OTTER_API_TOKEN=...
export OTTER_USERNAME=...
export OTTER_PASSWORD=...
export OTTER_TOTP_SEED=...

export OTTERDOG_CONFIG_ROOT="/path/to/your/otterdog-config"

otterdog web-login otterdog-<GitHub Username>
```

> **NOTE:** These environment variables must be re-exported in every new terminal session.


##### 2. Import and push the organization configuration

Import the current state of your GitHub organization and push the generated configuration to the `.otterdog` repository:

```shell
otterdog import otterdog-<GitHub Username>
otterdog push-config
```

This creates the initial jsonnet configuration file under `orgs/otterdog-<GitHub Username>/` in your config project.

##### 3. Fetch the remote configuration

Fetch the configuration stored in the remote `.otterdog` repository to ensure it is in sync with your local state:

```shell
otterdog fetch-config otterdog-<GitHub Username>
```

##### 4. Create a test repository

Edit the organization jsonnet configuration file:

```
/path/to/your/otterdog-config/orgs/otterdog-<GitHub Username>/otterdog-<GitHub Username>.jsonnet
```

Add a new repository entry:

```jsonnet
orgs.newRepo('test-repo') {
  description: "OtterDog test repository",
},
```

If the file contains org-level settings that conflict with the defaults (e.g. settings already defined in `otterdog-defaults.libsonnet`), remove the duplicates. For example, the following block can be trimmed down to only the settings you want to override:

```jsonnet
orgs.newOrg('otterdog-<GitHub Username>', 'otterdog-<GitHub Username>') {
  settings+: {
    members_can_change_repo_visibility: true,
    members_can_create_private_pages: true,
    members_can_create_private_repositories: true,
    members_can_create_public_repositories: true,
    members_can_create_teams: true,
    members_can_delete_repositories: true,
  },
```

Apply the changes to GitHub:

```shell
otterdog apply otterdog-<GitHub Username>
otterdog push-config otterdog-<GitHub Username>
```

#### Test otterdog PR

Clone the `.otterdog` repository:

```bash
git clone https://github.com/otterdog-<GitHub Username>/.otterdog
```

Change description of `test-repo`:

Edit the organization jsonnet configuration file:

```
/path/to/your/otterdog-config/orgs/otterdog-<GitHub Username>/otterdog-<GitHub Username>.jsonnet
```

Change `repo-test` description:

```jsonnet
orgs.newRepo('test-repo') {
  description: "OtterDog test repository from PR",
},
```

Create a specific branch and commit the modification:

```shell
git checkout -b "feat/repo_desc"
git add .
git commit -s -m "feat: change repo-test description"
git push origin "feat/repo_desc"
```

Then open a PR from this branch: `https://github.com/otterdog-<GitHub Username>/.otterdog/pull/new/feat/repo_desc`
