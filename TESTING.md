# Local testing

In order to run a development version of the `otterdog` app locally you need to set up a GitHub app and
configure `otterdog` to use it:

### Create a GitHub App

Create a GitHub app with the following permissions and events:

Repository Permissions:

- Actions: read and write
- Administration: read and write
- Commit statuses: read and write
- Contents: read and write
- Environments: read and write
- Issues: read only
- Metadata: read only
- Pages: read and write
- Pull requests: read and write
- Secrets: read and write
- Variables: read and write
- Webhooks: read and write
- Workflows: read and write

Organization Permissions:

- Administration: read and write
- Custom Organization Roles: read and write
- Members: read only
- Plan: read only
- Secrets: read and write
- Variables: read and write
- Webhooks: read and write

Events:

- Issue comment
- Pull request
- Pull request review
- Push
- Workflow job
- Workflow run

Configure a webhook using a [smee.io](https://smee.io) channel and set up a secret.

Generate and download the private key for the generated GitHub app.

### Otterdog config repository

You need to set up a config repository that contains the `otterdog.json` file that primarily contains
the mapping between `project name` and `organization id` of a project. This file is also needed for the
cli part of `otterdog` to work properly.

In order to receive updates from this config repository automatically in the local instance of `otterdog` as
well, you can set up a webhook to the same `smee.io` channel as configured for the GitHub app (see above).
You only need to configure `push` events for this webhook.

An example for an `otterdog.json` looks like that:

```json
{
  "defaults": {
    "bitwarden": {
      "api_token_key": "api_token_admin"
    },
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
      "name": "OtterdogTest",
      "github_id": "OtterdogTest",
      "credentials": {
        ...
      }
    }
  ]
}
```

### Environment

Create a `.env` file in the `otterdog` root directory and adjust the contents as outlined:

```dotenv
DEBUG=True
BASE_URL=http://localhost:5000
CACHE_CONTROL=False
APP_ROOT=/app/work

OTTERDOG_CONFIG_OWNER=<GitHub organization hosting the otterdog.json, e.g. OtterdogTest>
OTTERDOG_CONFIG_REPO=<GitHub repo hosting the otterdog.json, e.g. otterdog-configs>
OTTERDOG_CONFIG_PATH=<Path to the otterdog.json, e.g. otterdog.json>
OTTERDOG_CONFIG_TOKEN=<a valid GitHub token, no need for any permissions, just for rate limit purposes>

GITHUB_ADMIN_TEAMS=<comma separated list of teams>
GITHUB_WEBHOOK_ENDPOINT=/github-webhook/receive
GITHUB_WEBHOOK_SECRET=<the webhook secret as configured for the GitHub App>
GITHUB_WEBHOOK_VALIDATION_CONTEXT=<the validation context, e.g. otterdog/otterdog-validation>
GITHUB_WEBHOOK_SYNC_CONTEXT=<the sync context, e.g. otterdog/otterdog-sync>

GITHUB_APP_ID=<app id>
GITHUB_APP_PRIVATE_KEY=<path to the private key file>

DEPENDENCY_TRACK_URL=<base url to your dependency track installation, e.g. https://sbom.eclipse.org>
DEPENDENCY_TRACK_TOKEN=<api key with at least BOM_UPLOAD permissions>
```

`GITHUB_WEBHOOK_VALIDATION_CONTEXT` is used as the name for the validation
check reported to GitHub PRs that's run by the webapp. You can put any string
here and match the same string in GitHub Branch Protection to require the check.
`GITHUB_WEBHOOK_SYNC_CONTEXT` is used as the name for the sync check reported
to GitHub PRs that's run by the webapp. You can put any string here and match
the same string in GitHub Branch Protection to require the check.

### Webhook forwarding

You can use `https://smee.io` to forward webhook events sent by GitHub to your local machine.
Install the `smee.io` cli tool and create a script like that (replace `<channel>` according to the channel you created):

```bash
#!/bin/bash
smee -u https://smee.io/<channel> --target http://127.0.0.1:5000/github-webhook/receive
```

### Start the local development version

Build a docker image of otterdog the first time you want to run `otterdog` locally:

```bash
cd docker
./control.sh build
```

Start the local development instance:

```bash
cd docker
./control.sh startdev
```

Note: there is no need to rebuild the docker image everytime you want to run `otterdog` locally. The docker compose configuration
mounts the source code into the container. Also debug / reloader mode is enabled, so code or template changes should trigger an app restart
for quick testing.
