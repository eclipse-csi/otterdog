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

## Organization settings related to security

- `security_managers` lists the teams that get the security manager role, which grants access to the security
  alerts and settings of all repositories, see
  [Managing security managers](https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/managing-security-managers-in-your-organization).
- `default_code_security_configurations_disabled: true` removes the default
  [code security configurations](https://docs.github.com/en/code-security/securing-your-organization/introduction-to-securing-your-organization-at-scale/about-enabling-security-features-at-scale)
  of the organization, so that the security settings of repositories are only defined by the otterdog
  configuration. Setting it to `false` does not create a default configuration.

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
