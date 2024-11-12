# Restrict usage of macOS large runners

To use a `macOS large runner` with GitHub Actions, one can just add something like that in a workflow file:

``` yaml
  runs-on: macos-latest-large
```

This will incur quite some costs as such runners are considerably more expensive than normal ones
(see [Billing for GitHub Actions](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions)).

This policy allows to control which organization / project is entitled to use such runners. If an organization is disallowed to use them,
any workflow job that is queued on matching macOS large runners will be cancelled.

## Configuration

- `type` - `macos_large_runners`

### Settings

| Setting   | Necessity | Value type                                   |
|-----------|-----------|----------------------------------------------|
| allowed   | mandatory | boolean                                      |

## Example

``` yaml
name: Restrict use of macOS large runners
description: |-
  This policy restricts the use of macOS large runners for workflows using GitHub actions.
  If disallowed for an organization, any workflow job that uses such a runner is cancelled.
  In case your project wants / needs to use such runners, please open a ticket at the [HelpDesk](https://gitlab.eclipse.org/eclipsefdn/helpdesk/-/issues/new).
type: macos_large_runners
config:
  allowed: false
```
