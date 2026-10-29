# Repository security features

GitHub provides several security features per repository. With otterdog, they are configured as
[repository](../../reference/organization/repository/index.md) settings, so that a common baseline can be defined in
the default configuration and exceptions are visible in the configuration of the organization.

| Need                                                      | Repository settings                                                          |
|-----------------------------------------------------------|------------------------------------------------------------------------------|
| Detect leaked credentials and block them on push          | `secret_scanning`, `secret_scanning_push_protection`                          |
| Get alerts and fixes for vulnerable dependencies          | `dependabot_alerts_enabled`, `dependabot_security_updates_enabled`           |
| Let researchers report vulnerabilities privately          | `private_vulnerability_reporting_enabled`                                     |
| Analyze the code for vulnerabilities                      | `code_scanning_default_setup_enabled` and related settings                   |
| Apply the same features to many repositories              | `code_security_configuration`, see [Code security configurations](#code-security-configurations) |

The following example enables all of them for a public repository. Secret scanning, push protection and Dependabot
alerts are already enabled by the example default configuration:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') {
      dependabot_security_updates_enabled: true,
      private_vulnerability_reporting_enabled: true,
      code_scanning_default_setup_enabled: true,
      code_scanning_default_languages+: [
        "actions",
        "python",
      ],
    },
  ],
}
```

!!! note

    These features are free for public repositories. For private and internal repositories, secret scanning and
    code scanning require GitHub Secret Protection and GitHub Code Security, and otterdog does not manage secret
    scanning, push protection, Dependabot security updates and private vulnerability reporting, see
    [About secret scanning](https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning)
    and [Configuring default setup for code scanning](https://docs.github.com/en/code-security/code-scanning/enabling-code-scanning/configuring-default-setup-for-code-scanning).

## Secret scanning and push protection

Secret scanning detects credentials committed to the repository, push protection rejects pushes that contain them.
Push protection requires secret scanning: disabling `secret_scanning` while `secret_scanning_push_protection` is
enabled is reported as an error, so both settings must be disabled together.

!!! tip "Recommendation"

    Keep both enabled for all repositories. If a repository contains test data that looks like credentials,
    prefer excluding the paths in a `secret_scanning.yml` file over disabling the feature, see
    [Excluding folders and files from secret scanning](https://docs.github.com/en/code-security/secret-scanning/using-advanced-secret-scanning-and-push-protection-features/excluding-folders-and-files-from-secret-scanning).

## Dependabot

`dependabot_alerts_enabled` reports dependencies with known vulnerabilities, `dependabot_security_updates_enabled`
additionally opens pull requests that update them. Version updates, which keep dependencies up to date regardless
of vulnerabilities, are configured in a `.github/dependabot.yml` file of the repository, not in otterdog. The
[Required File](../../reference/blueprints/required-file.md) blueprint can ensure that such a file exists.

## Private vulnerability reporting

`private_vulnerability_reporting_enabled` lets security researchers report vulnerabilities through a private form
of a public repository, see
[Configuring private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/working-with-repository-security-advisories/configuring-private-vulnerability-reporting-for-a-repository).

!!! info "Organization policy"

    Enable private reporting only if someone triages the reports. Document how to report vulnerabilities in a
    `SECURITY.md` file, which a [Required File](../../reference/blueprints/required-file.md) blueprint can add to the
    `.github` repository of the organization.

## Code scanning

Default setup lets GitHub configure and run CodeQL. It is configured with:

- `code_scanning_default_setup_enabled`: enables default setup
- `code_scanning_default_languages`: the languages to analyze
- `code_scanning_default_query_suite`: `default` or `extended`

The languages and the query suite are only taken into account when default setup is enabled.

### Supported languages

`code_scanning_default_languages` only accepts the language identifiers of CodeQL, not the names of the languages
that GitHub shows for a repository. Some identifiers cover several languages, which cannot be selected separately:

| Value                   | Analyzes                                         | Languages detected by GitHub   |
|-------------------------|--------------------------------------------------|--------------------------------|
| `actions`               | GitHub Actions workflows                         | always accepted                |
| `c-cpp`                 | C and C++                                        | C, C++                         |
| `csharp`                | C#                                               | C#                             |
| `go`                    | Go                                               | Go                             |
| `java-kotlin`           | Java and Kotlin                                  | Java, Kotlin                   |
| `javascript`            | JavaScript                                       | JavaScript                     |
| `python`                | Python                                           | Python                         |
| `ruby`                  | Ruby                                             | Ruby                           |
| `swift`                 | Swift                                            | Swift                          |
| `rust`                  | Rust                                             | Rust                           |
| `typescript`            | TypeScript                                       | TypeScript                     |

!!! note "Deprecated: `javascript-typescript`"

    GitHub no longer reports `javascript-typescript`, it returns `javascript` and `typescript` separately. Existing
    configurations that still list `javascript-typescript` keep working: otterdog translates it to `javascript` and
    `typescript` when loading the configuration. Replace it with the two values to get rid of the deprecated one.
    If both are configured, `validate` only requires one of them to be detected in the repository, as CodeQL analyzes
    them together.

Any other value is rejected as soon as the configuration is loaded, e.g. by `validate` or `plan`: `java`, `kotlin`,
`c` or `cpp`, as well as languages that CodeQL does not analyze, e.g. PHP, Scala, Shell
or Jsonnet. These values follow the
[REST API for default setup](https://docs.github.com/en/rest/code-scanning/code-scanning#update-a-code-scanning-default-setup-configuration),
which documents all of them except `rust`: CodeQL analyzes Rust in default setup since its general availability in
October 2025, see the [GitHub changelog](https://github.blog/changelog/2025-10-14-codeql-scanning-rust-and-c-c-without-builds-is-now-generally-available).
The languages supported by CodeQL are listed in
[Supported languages and frameworks](https://codeql.github.com/docs/codeql-overview/supported-languages-and-frameworks/).

### Languages must be detected in the repository

`validate` also checks each configured language against the languages that GitHub detects in the repository, which
are shown in the sidebar of the repository: a language that is not detected, e.g. `python` for a repository without
Python code, is reported as error, with the list of detected languages. Only `actions` is always accepted.

As a consequence, languages can only be configured for repositories that already exist and contain code: create
the repository first, then configure the languages in a second change. A new repository can enable default setup
without languages:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-new-repo') {
      code_scanning_default_setup_enabled: true, // (1)!
    },
  ],
}
```

1. Without configured languages, the languages to analyze are left to GitHub. Once the repository contains code,
   configure the languages explicitly, so that the configuration shows what is analyzed.

Once the repository contains code, e.g. Java, Kotlin and TypeScript code as well as workflows, the languages are
configured with their CodeQL identifiers:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [
    orgs.newRepo('my-repo') {
      code_scanning_default_setup_enabled: true,
      code_scanning_default_languages+: [
        "actions",
        "java-kotlin", // (1)!
        "javascript",
        "typescript",
      ],
      code_scanning_default_query_suite: "extended", // (2)!
    },
  ],
}
```

1. A single identifier for Java and Kotlin, listing `java` or `kotlin` is rejected.
2. The `extended` suite runs additional queries, which find more problems but also report more false positives.

!!! warning

    Default setup and advanced setup (a custom CodeQL workflow) exclude each other: enabling default setup disables
    the existing CodeQL workflow and blocks its uploads. If a repository uses a custom workflow, keep
    `code_scanning_default_setup_enabled` disabled.

## Code security configurations

A [code security configuration](../../reference/organization/code-security-configuration.md) groups the security
features of the organization, and GitHub applies them to the repositories the configuration is attached to. A
configuration is attached to a repository with its `code_security_configuration` property:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  code_security_configurations+: [
    orgs.newOrgCodeSecurityConfiguration('baseline') {
      description: "Secret scanning and Dependabot for all repositories",
      code_security: "enabled", // (1)!
      secret_protection: "enabled",
      dependabot_alerts: "enabled",
      dependabot_security_updates: "enabled",
      secret_scanning: "enabled",
      secret_scanning_push_protection: "enabled",
      private_vulnerability_reporting: "enabled",
    },
  ],
  _repositories+:: [
    orgs.newRepo('my-repo') {
      code_security_configuration: "baseline", // (2)!
    },
  ],
}
```

1. GitHub requires `secret_protection` for the secret scanning features, and `code_security` for the code scanning
   ones. Without an unbundled GitHub Advanced Security plan, which is not available for an organization with free
   plan, both products must have the same status.
2. The settings of the repository that the configuration sets, e.g. `dependabot_alerts_enabled`, are not managed on
   the repository anymore, the configuration takes precedence. A repository without `code_security_configuration`
   keeps the configuration attached to it on GitHub.

!!! warning

    The features of `newOrgCodeSecurityConfiguration` are disabled by default, except the dependency graph: attaching
    a configuration disables the features it does not enable on the repository, e.g. code scanning default setup.
    Set a feature to `not_set` to leave it to the repositories.

### Default configuration for new repositories

`default_for_new_repos` attaches a configuration to the new repositories of a visibility, `all`, `public` or
`private_and_internal`, when GitHub creates them. The organization setting
`default_code_security_configurations_disabled` removes any default configuration, it has to be disabled:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    default_code_security_configurations_disabled: false, // (1)!
  },
  code_security_configurations+: [
    orgs.newOrgCodeSecurityConfiguration('public-baseline') {
      code_security: "enabled",
      secret_protection: "enabled",
      dependabot_alerts: "enabled",
      secret_scanning: "enabled",
      secret_scanning_push_protection: "enabled",
      default_for_new_repos: "public", // (2)!
    },
  ],
}
```

1. Otherwise, the validation reports an error, as the setting would remove the default configuration again.
2. A visibility can have one default configuration only, `all` covers both `public` and `private_and_internal`.

### Delegated bypass of push protection

With delegated bypass, pushing a secret requires the approval of a reviewer, a team or a role referenced like the
[bypass actors](../../reference/organization/repository/bypass-actor.md) of rulesets. The suffix `:exempt` exempts a
reviewer from push protection instead, e.g. for automation:

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  code_security_configurations+: [
    orgs.newOrgCodeSecurityConfiguration('baseline') {
      code_security: "enabled",
      secret_protection: "enabled",
      secret_scanning: "enabled",
      secret_scanning_push_protection: "enabled",
      secret_scanning_delegated_bypass: "enabled",
      secret_scanning_delegated_bypass_reviewers: [
        "@my-org/security-team",
        "#OrganizationAdmin",
        "@my-org/release-bots:exempt",
      ],
    },
  ],
}
```

!!! warning

    The configurations of the organization that are not defined in the otterdog configuration are deleted with
    `--delete-resources`, and listed as deletions by `plan` otherwise. GitHub created such configurations for the
    organizations that existed in March 2024, e.g. `Legacy - public repositories`, from their former settings for new
    repositories. Delete them if no repository is attached to them, or import them to keep them. The predefined
    configurations of GitHub, e.g. `GitHub recommended`, are not managed.

!!! note

    For private and internal repositories, `code_security` and `secret_protection` enable GitHub Code Security and
    GitHub Secret Protection, which are licensed per active committer, they are free for public repositories.
    Enabling them in a configuration attached to private repositories, or attaching a private repository to a
    configuration enabling them, is thus considered to be cost-related, except for an organization with free plan,
    for which they cannot be purchased. A configuration enabling them for public repositories only can be
    auto-merged.

## Organization settings related to security

- `security_managers` lists the teams that get the security manager role, which grants access to the security
  alerts and settings of all repositories, see
  [Managing security managers](https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/managing-security-managers-in-your-organization).
- `default_code_security_configurations_disabled: true` removes the default code security configurations of the
  organization, including the predefined ones of GitHub. Set it to `false` to use a
  [default configuration for new repositories](#default-configuration-for-new-repositories), it does not create one
  by itself.

``` jsonnet
orgs.newOrg('my-project', 'my-org') {
  settings+: {
    security_managers+: [
      "security-team",
    ],
  },
  teams+: [
    orgs.newTeam('security-team') {
      description: "Triages security alerts and vulnerability reports",
    },
  ],
}
```
