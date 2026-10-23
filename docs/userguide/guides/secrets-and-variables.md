# Secrets and variables

Workflows often need credentials, e.g. to publish packages or sign artifacts, and configuration values. GitHub
Actions provides secrets for sensitive values and variables for other values. Otterdog manages both on
organization, repository and environment level.

| Scope        | Properties                                                                    | Available to                                                     |
|--------------|-------------------------------------------------------------------------------|------------------------------------------------------------------|
| Organization | [`secrets`](../../reference/organization/secret.md), [`variables`](../../reference/organization/variable.md) | the repositories selected by `visibility`  |
| Repository   | [`secrets`](../../reference/organization/repository/secret.md), [`variables`](../../reference/organization/repository/variable.md) | all workflows of the repository |
| Environment  | [`secrets`](../../reference/organization/repository/environment/secret.md), [`variables`](../../reference/organization/repository/environment/variable.md) | jobs that use the environment, once its protection rules pass |

The `visibility` of organization secrets and variables can be:

- `public`: all repositories of the organization
- `private`: private and internal repositories, not available for organizations on the `free` plan
- `selected`: only the repositories listed in `selected_repositories`

## Reference secret values, never write them

Secret values must not be written in the configuration, which is stored in a repository. Instead, reference
them in a credential provider with the format `<provider>:<data>`, e.g. `pass:path/to/secret`. Otterdog resolves
the reference when it applies the configuration. The supported providers and their formats are listed in
[SecretValue](../../reference/organization/secret-value.md), and `validate` reports secret values that do not use
a credential provider as warning.

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  secrets+: [
    orgs.newOrgSecret('SIGNING_KEY') {
      value: "pass:path/to/signing-key",
      visibility: "selected",
      selected_repositories+: [
        "my-library",
      ],
    },
  ],
  variables+: [
    orgs.newOrgVariable('REGISTRY_URL') {
      value: "https://registry.example.org",
    },
  ],
  _repositories+:: [
    orgs.newRepo('my-library') {
      secrets+: [
        orgs.newRepoSecret('DOCS_DEPLOY_TOKEN') {
          value: "pass:path/to/docs-deploy-token",
        },
      ],
      environments+: [
        orgs.newEnvironment('publish') {
          deployment_branch_policy: "selected",
          branch_policies+: [
            "tag:v*",
          ],
          secrets+: [
            orgs.newEnvSecret('REGISTRY_TOKEN') {
              value: "pass:path/to/registry-token",
            },
          ],
        },
      ],
    },
  ],
}
```

!!! tip "Recommendation"

    Give each secret the narrowest scope that works: an environment secret for deployment credentials, protected
    by the rules of the environment (see [Deployment environments](environments.md)), a repository secret for a
    single repository, and an organization secret with `selected` visibility for credentials that several
    repositories share. A secret with `public` visibility is available to every repository, including
    repositories created later.

## Override a value for a repository or an environment

When secrets or variables with the same name are defined on several levels, the most specific one is used: an
environment value takes precedence over a repository value, which takes precedence over an organization value, see
[Using secrets in GitHub Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).
This allows defining a value for most repositories and overriding it where needed:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  variables+: [
    orgs.newOrgVariable('REGISTRY_URL') {
      value: "https://registry.example.org", // (1)!
    },
  ],
  _repositories+:: [
    orgs.newRepo('my-library') {
      variables+: [
        orgs.newRepoVariable('REGISTRY_URL') {
          value: "https://staging.registry.example.org", // (2)!
        },
      ],
      environments+: [
        orgs.newEnvironment('release') {
          variables+: [
            orgs.newEnvVariable('REGISTRY_URL') {
              value: "https://registry.example.org", // (3)!
            },
          ],
        },
      ],
    },
  ],
}
```

1. Used by all repositories, `public` being the default visibility of organization variables in the example
   default configuration.
2. Used by the workflows of `my-library`, e.g. to publish snapshots to a staging registry.
3. Used by the jobs of `my-library` that run in the `release` environment.

!!! tip "Recommendation"

    Overriding a secret hides which value a workflow actually uses. Prefer distinct names, e.g. `STAGING_TOKEN` and
    `RELEASE_TOKEN`, for secrets that grant different permissions, and keep overrides for configuration values.

## Secrets managed outside otterdog

A secret with the redacted value `********`, which `import` writes as GitHub never discloses secret values, is
skipped by otterdog, see [Redacted values](../../reference/organization/secret-value.md#redacted-values). Such a
secret can be maintained in the GitHub web interface.

!!! info "Organization policy"

    Managing secrets with otterdog makes them visible in the configuration and centralizes their rotation, but only
    people with access to the credential provider can change them. Keeping a secret as `********` lets maintainers
    of a repository manage it themselves, but it is not visible which value is used and when it was rotated.

## Updating secret values

Otterdog cannot detect that the value of a secret changed in the credential provider. After rotating a
credential, update the secret explicitly, see [Updating values](../../reference/organization/secret-value.md#updating-values).

## Avoid long-lived secrets

Many cloud providers and package registries accept short-lived tokens that a workflow obtains with OpenID Connect,
without storing any secret in GitHub, see
[OpenID Connect](https://docs.github.com/en/actions/concepts/security/openid-connect). Combined with a protected
environment, this is usually safer than a long-lived token stored as secret.

## Limits

- Secret names must not start with `GITHUB_`.
- Secrets and variables of Dependabot, Codespaces and Copilot agents cannot be managed with otterdog, see
  [Unsupported Features](../unsupported.md). GitHub moved the secrets of the Copilot cloud agent from an
  environment named `copilot` to dedicated agent secrets, see the
  [GitHub changelog](https://github.blog/changelog/2026-05-11-more-flexible-secrets-and-variables-for-copilot-cloud-agent/).
