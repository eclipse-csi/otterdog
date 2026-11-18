---
name: otterdog-operation
description: Add or change an otterdog operation, meaning a class in otterdog/operations/ together with the Click command in otterdog/cli.py that runs it once per organization. Covers the execution contract (several organizations, confirmation and --force, partial failures, exit codes, output), the structure of the class, its options, error handling, tests at the operation and Click levels, and the CLI reference docs. Use it when asked for a new otterdog CLI command, a new option of an existing command, or a fix to how an operation reports errors or results.
---

# Add or change an otterdog operation

The conventions, commands and GitHub safety rules are in `AGENTS.md`.

## When to use

- A new `otterdog <command>`, or a new option or behaviour of an existing command.
- Wrong error handling, exit codes or output in an operation.

Changes to how the diff is computed belong to the models; see the `github-config-property` skill. The webapp tasks
in `otterdog/webapp/tasks/` also run `PlanOperation`, `LocalPlanOperation` and `LocalApplyOperation`, the last one a
subclass of `ApplyOperation`: a change to `ApplyOperation` also affects them, even when the request is about the CLI
only. Check those callers when you change `diff_operation.py`, `plan.py`, `apply.py`, `local_plan.py` or
`local_apply.py`.

## 1. Define the execution contract

Before writing the class, decide what the user observes in each of these cases:

- **Several organizations.** `_execute_operation` in `cli.py` runs `execute()` for each organization in turn and
  exits with the highest code returned. After a handled failure (a non-zero return), the next organizations still
  run. An exception that escapes `execute()` stops the remaining organizations and exits with `2`; a
  `KeyboardInterrupt` exits with `130`. Decide whether a failure for one organization must stop the others.
- **Exit codes.** `0` on success and `1` on a handled failure. `ApplyOperation` returns the number of validation
  errors, or the number of patches that failed to apply, and a refused confirmation returns `0` with
  `Apply cancelled.` State what your command returns in each case.
- **Confirmation**, for a command that writes to GitHub: what it covers (the actions printed before the prompt),
  when it comes (after every read and validation, before the first write), and what a refusal produces (message,
  exit code, and no write at all). `--force` skips only the confirmation: validations still run, and destructive
  options stay separate and opt-in, as `--delete-resources` for `apply`. The webapp has no terminal: it builds
  `LocalApplyOperation(force_processing=True, ...)` in `webapp/tasks/apply_changes.py`, so an operation it runs must
  never reach `get_approval()`.
- **Partial writes.** If the command sends several mutations, decide what the summary reports after a failure
  halfway, and what a rerun does. A one-shot action is not idempotent: running `dispatch-workflow` twice dispatches
  the workflow twice.
- **Output.** The printer of the CLI writes to stdout, errors included (`print_error`); statistics go to stderr, to
  keep structured output intact (`_report_api_usage`). If the command has machine-readable output, such as `--json`
  of `list-apps` and `check-status`, decide where its diagnostics go so that they do not corrupt it.

## 2. Pick a model to copy

| Kind of operation                          | Example to copy                                         |
|--------------------------------------------|---------------------------------------------------------|
| Reads the local configuration only         | `show.py`, `canonical_diff.py`                          |
| Reads GitHub with a token                  | `list_members.py`, `list_apps.py`, `list_advisories.py` |
| Changes GitHub, with a confirmation        | `apply.py`, `push_config.py`, `review_app_permissions.py` |
| Computes a diff between config and GitHub  | subclass `DiffOperation` / `PlanOperation` (`diff_operation.py`, `plan.py`) |
| Does not depend on an organization         | `list_projects.py` (`SingletonCommand`)                 |

`delete_file.py` and `dispatch_workflow.py` also change GitHub, but ask for no confirmation: do not copy that part.

## 3. Operation class (`otterdog/operations/<name>.py`)

Start with the EPL-2.0 header, `from __future__ import annotations`, and `OrganizationConfig` imported under
`TYPE_CHECKING`. Subclass `Operation` (`otterdog/operations/__init__.py`):

- `__init__`: call `super().__init__()`, store the options in private attributes, and expose them with read-only
  properties.
- `pre_execute()`: print a single header line that describes the run. It is called once, before the first
  organization.
- `async execute(org_config, org_index, org_count) -> int` is called once per organization:
    1. `self._print_project_header(org_config, org_index, org_count)`, then `self.printer.level_up()`, with
       `self.printer.level_down()` in a `finally` block.
    2. Only the steps the operation needs. An operation that only reads or calls GitHub may need neither the
       template nor the configuration, as `dispatch_workflow.py`.
        - Template and configuration: `await org_config.jsonnet_config.init_template()`, then
          `check_config_file_exists(...)` and `GitHubOrganization.load_from_file(...)`; report a `RuntimeError` with
          `print_error(f"failed to load configuration: {escape(str(ex))}")`.
        - Credentials: `self.get_credentials(org_config, only_token=True)`; pass `only_token=False` only when a web
          UI login is required. Report a `RuntimeError` as `invalid credentials`.
        - GitHub: `async with GitHubProvider(credentials) as provider:`, with the clients' `RuntimeError` reported
          as a failure of the action.
    3. Put each `try` around the call that raises, not around several steps: one `except RuntimeError` for the
       whole method would report a loading or execution error as `invalid credentials`.
    4. Return the code that the contract of step 1 defines.
- `post_execute()` is optional. Use it for a summary across organizations.

Error handling:

- Expected failures (missing file, invalid credentials, GitHub errors that a client wrapped in `RuntimeError`) are
  reported with `self.printer.print_error(...)` and a non-zero return. Never let them escape as tracebacks, and do
  not call `sys.exit` in an operation. `BadCredentialsException` and `InsufficientPermissionsException`
  (`otterdog/providers/github/exception.py`) are not `RuntimeError`s: an `except RuntimeError` lets them through,
  and the command then exits with `2` and skips the remaining organizations.
- Escape untrusted text with `rich.markup.escape` before printing it, because the printer interprets Rich markup.
  Escaping does not hide anything: an error message from GitHub or a client can contain tokens, secret values or
  URLs with credentials. Remove them before printing; otterdog has no shared helper for it, so never print request
  headers or bodies.

Confirmation: print the planned actions, then call `get_approval()` from `otterdog/utils.py`, unless `--force` is
given. See `ApplyOperation.handle_finish` in `apply.py` and `check_config_file_overwrite_if_exists` in
`operations/__init__.py`.

## 4. CLI command (`otterdog/cli.py`)

- Use `@cli.command(cls=StdCommand)`. It adds the `organizations` argument (all organizations when the argument is
  omitted) and `--config`, `--local`, `--verbose`, `--stats` and `--stats-file`. Use `SingletonCommand` for a
  command that does not take organizations.
- Declare the options with `@click.option` and the help text with a docstring or `short_help`. Then import the
  operation inside the function, as the other commands do, and call
  `_execute_operation(organizations, <Operation>(...))`.

## 5. Tests

- Add tests to `tests/operations/test_<name>.py`. Stub the printer with `pretend` (`test_list_advisories.py`) or
  use an `IndentingPrinter` that writes to a `StringIO` (`test_operation.py`). Mock `GitHubProvider` and the REST
  clients; never call GitHub.
- Cover the success path, every handled failure and its exit code.
- **Refused confirmation, first**, for a command that changes GitHub: invoke it through Click
  (`CliRunner().invoke(cli.cli, [...])`, as `tests/test_cli_no_web_ui.py` does) with `get_approval` patched to return
  `False`. Check the exit code, the message, and that no mutation was sent. This also exercises the options from
  Click to the operation. Then check that `--force` never calls `get_approval`, that the validations still run, and
  that destructive options stay off unless given.
- **Two organizations**: with the `run_operation` fixture of `tests/test_cli_stats.py`, which runs
  `_execute_operation` over two organizations, make the first one fail in a handled way. The fixture is defined in
  that file, not in a conftest, and its `org_config` stub only has `name` and `github_id`: move it to a conftest or
  extend the stub when your operation needs more. Check whether the second
  runs as the contract says, and the final exit code. A unit test of `execute()` that returns `1` does not catch a
  regression in this orchestration.
- **Partial writes**: a failure halfway gives the summary of the contract, and a rerun does what the contract says.
- **Webapp**: if a webapp task runs the operation, test that path without a terminal: `get_approval` is never called.
- **Machine-readable output**: test its format, and that diagnostics do not end up in it.
- `poetry run otterdog <command> --help` checks that the command is registered.

## 6. Documentation

- List the command in the output block of `docs/reference/operations/index.md`.
- A user-facing command with options deserves its own page in `docs/reference/operations/` (see `apply.md`), with a
  nav entry under "CLI Operations" in `zensical.toml`.

## 7. Checks

Choose the checks with the rules in `AGENTS.md`. For a typical operation they are:

```shell
poetry run prek run --files otterdog/cli.py otterdog/operations/<name>.py tests/operations/test_<name>.py
poetry run pytest tests/operations tests/test_cli_stats.py tests/test_cli_no_web_ui.py
make docs   # docs changed
```

Run `make test` when `Operation`, `DiffOperation`, `PlanOperation` or `cli.py` helpers shared by all commands
changed. Run the command against an organization only when the user explicitly asks; see `AGENTS.md`.
