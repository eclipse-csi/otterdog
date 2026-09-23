<!--
Thank you for contributing to otterdog!
Please fill in the sections below. Remove any section that does not apply,
but keep the Testing section — Please describe how the change was validated. Changes requiring tests
should include appropriate test coverage.
-->

## Description

<!-- What does this PR do? Explain the motivation and the change itself. -->

### Related issue

<!-- Link the issue this PR addresses, e.g. "Fixes #123" or "Relates to #123". -->

Fixes #

### Type of change

<!-- Check all that apply. -->

- [ ] 🐛 Bug fix (non-breaking change fixing an issue)
- [ ] ✨ New feature (non-breaking change adding functionality)
- [ ] 💥 Breaking change (fix or feature that changes existing behavior, config schema, or default template)
- [ ] 📝 Documentation only
- [ ] 🔧 Refactoring / internal change (no functional change)

### Breaking change details

<!-- If this is a breaking change: what breaks, who is affected (CLI users,
webapp deployments, existing otterdog.json / jsonnet configs), and what is
the migration path? Remove this section otherwise. -->

## Tests

<!--
A unit test or test suite is the minimum requirement:
- New feature: unit tests (or a test suite under `tests/`) are mandatory,
  especially for substantial PRs.
- Bug fix: if no test currently covers the bug, add an equivalent unit test
  reproducing it whenever possible.
-->

- [ ] Unit tests added / updated under `tests/`
- [ ] No test added

### Manual testing

<!-- otterdog behavior differs between GitHub plans (e.g. rulesets, branch
protections, custom roles are plan-dependent) — always state the plan used.
Check everything that was actually exercised and fill in the details. -->

- [ ] GitHub API calls only stubbed / mocked in unit tests (no live testing)
- [ ] Tested on a real GitHub organization (live GitHub API):
  - Organization(s) used: <!-- e.g. OtterdogTest -->
  - GitHub plan: <!-- Free / Team / Enterprise Cloud -->
  - [ ] **CLI** — commands run: <!-- e.g. `otterdog plan`, `otterdog apply`, `otterdog validate`, ... -->
  - [ ] **Web app** — pages / flows exercised:
  - [ ] **Webhook interactions** — otterdog bot behavior on PRs (validation / sync checks, bot comments on the config repo PRs); org plan used: <!-- Free / Team / Enterprise Cloud -->

### How to reproduce / test scenario:**

<!-- Step by step, so a reviewer can reproduce your testing, e.g.:
1. Configure `otterdog.json` with organization X (Free plan)
2. Run `otterdog plan -c otterdog.json X`
3. Open a PR on the `.otterdog` config repo and check the bot validation comment
-->

### Screenshots

<!-- Required for changes affecting the web app UI or the bot account
messages/checks on PRs. Remove otherwise. -->

## Checklist

- [ ] Documentation updated (`docs/`, reference docs for new/changed settings, `mkdocs` builds)
- [ ] Default template / examples updated if the config schema changed (`examples/template/otterdog-defaults.libsonnet`)

## Notes for reviewers

<!-- Points of attention: risky areas, design decisions, plan-dependent
behavior, parts you are unsure about, suggested review order. -->
