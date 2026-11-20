# Security Policy

This project follows the [Eclipse Foundation Baseline Security Policy](https://www.eclipse.org/security/baseline/).

## Reporting a Vulnerability

To report a vulnerability privately, open this repository's **Security**
tab and select **Report a vulnerability**.

You can also submit a confidential report through the
[Eclipse Foundation Vulnerability Reporting Tracker](https://gitlab.eclipse.org/security/vulnerability-reports/-/work_items/new?issue%5Bconfidential%5D=true).

Please use one of these private reporting channels, and do not report
vulnerabilities through public issues, pull requests, discussions or mailing
lists. Send your report as plain text without attachments. See the baseline
policy for what to include in your report and what to expect after submitting
it.

## Supported Versions

Only the latest release receives security fixes.

## Scope

Otterdog executes with the credentials of the organizations it manages. Some of its inputs are trusted and are equivalent
to code, in particular the `otterdog.json` configuration and the default configuration referenced by its
`base_template`, whose Python scripts otterdog executes. Issues that require control of such an input are not considered
vulnerabilities. The trusted and untrusted inputs are listed in the
[threat model](docs/threat-model.md#trusted-and-untrusted-inputs).
