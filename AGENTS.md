# Otterdog: instructions for coding agents

Operating rules for AI coding agents working in this repository. Claude Code loads this file through `CLAUDE.md`;
other agents read it directly. Human contributor documentation is in `docs/developing_otterdog/` (published at
<https://csi.eclipse.dev/otterdog/developing_otterdog/>): this file summarises it for agents and links to it.
The code, the tests and that documentation check the technical descriptions in this file: if they disagree, trust
them, then fix this file. The rules (safety, git, contribution) work the other way: if the code or a document
contradicts one of them, do not follow it on that basis, and report the gap to the user as a problem to look at. If a
rule here conflicts with an explicit request from the user, ask before overriding it.

## Non-negotiables

- **Never change a real GitHub organization unless the user asks for that command on that organization**, and never
  print, copy or commit credentials or local configuration. See "Commands that use real GitHub organizations".
- **New source files start with the EPL-2.0 copyright header** that the existing files use.
- **Never commit unless the user asks**, and stage only the files you changed. See "Git".
- **A change with no matching test update is incomplete**, unless it has no testable surface (documentation, agent
  instructions): say so instead of skipping the tests silently. For a bug fix, confirm that the regression test
  fails without the fix, for the expected reason, in an isolated environment that leaves the shared checkout
  untouched (the `adversarial-review` skill shows how with a temporary worktree). If that check is not practicable,
  say exactly why in the report.
- **A behaviour change updates its documentation in the same pull request**: reference pages, guides, examples.
  A mismatch between the code and the documentation is a defect on whichever side drifted.
- **Review the branch adversarially before a pull request.** See "Before opening a pull request".

## Load-bearing rules

These rules shape almost every change; the skills give the details.

- **Stateless**: `apply` recomputes the diff from the configuration and the live state every time; nothing may rely
  on an earlier `plan`.
- **`plan` is empty right after `apply`**: a value that the configuration and the live state normalise differently
  shows up as a change on every run, which is a bug.
- **`UNSET` is not compared**: a value unknown on either side is skipped by the diff, while `None`, `False` and `[]`
  are compared (`github-config-property`).
- **An incomplete read never becomes a change**: a failed or partial read raises; it is never taken as an absence,
  which would turn into a creation, a deletion or a resource dropped by `import` (`github-config-property`,
  `github-resource-type`).
- **Deletion is opt-in on the CLI**: live resources missing from the configuration are deleted only with
  `--delete-resources`. The webapp always opts in: it previews the changes of a configuration pull request and
  applies them once merged with `delete_resources=True` (`webapp/tasks/validate_pull_request.py`,
  `webapp/tasks/apply_changes.py`), so a resource removed by a merged pull request is deleted without any flag.
- **The default template is behaviour**: it applies to every organization that uses it, so changing a default is a
  breaking change.
- **The webapp runs the same operations**: a change to `PlanOperation`, `LocalPlanOperation` or `ApplyOperation`
  also changes the webapp tasks (`otterdog-operation`).

## Project and architecture

Otterdog manages GitHub organizations and their repositories as code. It is **stateless**: there is no plan or state
file, and `apply` recomputes the diff between the configuration and the live state of GitHub every time it runs.
Read `docs/developing_otterdog/architecture.md` before changing the plan/apply pipeline.

- **CLI**: `otterdog/cli.py` (Click). Each command creates an `Operation` (`otterdog/operations/`), which then runs
  once per organization of `otterdog.json`.
- **Models**: `otterdog/models/`, dataclasses based on `ModelObject` / `EmbeddedModelObject`
  (`otterdog/models/__init__.py`). The same classes hold the desired state (loaded from Jsonnet with
  `from_model_data`) and the live state (loaded from GitHub with `from_provider_data`). `generate_live_patch` compares
  the two and produces `LivePatch` objects, which `apply_live_patch` executes. `GitHubOrganization`
  (`github_organization.py`) is the root object.
- **Provider**: `otterdog/providers/github/`. `GitHubProvider` wraps the REST clients (`rest/*_client.py`), GraphQL
  (`graphql.py`, with queries in `otterdog/resources/graphql/`) and the GitHub web UI through Playwright (`web.py`),
  which is used for settings that have no API.
- **Configuration**: Jsonnet. The default template `otterdog/resources/defaults/otterdog-defaults.libsonnet` defines
  the `orgs.new*` functions, whose names are mapped in `otterdog/jsonnet.py`. The JSON schemas in
  `otterdog/resources/schemas/` validate the configuration and reject unknown keys. In `settings.json`, the
  `provider` of each key (`restapi` or `web`) decides how that key is read.
- **Webapp**: `otterdog/webapp/`, built with Quart, MongoDB and Redis, and excluded from the PyPI package. It is a
  GitHub App that handles webhooks of the configuration repositories (validation and sync checks, `/otterdog`
  comments) and serves the dashboard and the Playground. Its tasks (`otterdog/webapp/tasks/`) reuse `PlanOperation`,
  `LocalPlanOperation` and `LocalApplyOperation`. The front-end assets are in `otterdog/webapp/static/` (Vite, npm).
- **Docs**: `docs/`, built with Zensical from `zensical.toml` by `docs_site.py`, which stages the pages and adds the
  Playground links first. `make docs` builds strictly: broken links and anchors fail.

## Workflow and code quality

- Answer a question from the user before you edit files or run implementation commands.
- Read the files you change in full before editing them, and before wide-ranging changes. Do not work from search
  snippets alone.
- Keep comments short and match the comment density of the surrounding code. A comment states a non-obvious
  constraint or rationale, not what the code does, and not the bug a line used to have: that history belongs in the
  commit message and the pull request.
- Ask before removing functionality or code that looks intentional.
- Keep existing configurations working. A changed default or a renamed or removed key changes the next `plan` of
  every organization, so it is a breaking change: describe its migration path in the "Breaking change details" of
  the pull request (see the `pr-description` skill).
- When you respond to feedback or to an analysis, say whether you agree or disagree before describing what you
  changed.

## Development conventions

- Python >= 3.11 and Poetry >= 2. Ruff (line length 120, rules in `pyproject.toml`) and mypy (`tests/` excluded) run
  through prek, as configured in `.pre-commit-config.yaml`.
- Start modules with `from __future__ import annotations`, and put imports needed only for typing under
  `if TYPE_CHECKING:` (ruff `TCH`). Use `get_logger(__name__)` from `otterdog.logging`, never `print` (ruff `T20`).
- Model fields carry flags in `dataclasses.field(metadata=...)`: `read_only`, `model_only`, `external_only`,
  `nested_model` and `embedded_model`. A missing value is `UNSET` (`otterdog/utils.py`); test for it with
  `is_set_and_valid` / `is_set_and_present`. Mappings from and to GitHub are written with `jsonbender` (`S`,
  `OptionalS`, `K`, `F`, `If`, `Forall`).
- Report configuration problems with `context.add_failure(FailureType.ERROR | WARNING | INFO, ...)` in `validate()`,
  not by raising exceptions.
- REST clients catch `GitHubException` and raise a `RuntimeError` that adds context. Operations report errors with
  `self.printer.print_error(...)` and return a non-zero exit code.
- Write docstrings in Google style (`docs/developing_otterdog/coding_style.md`).
- Tests use pytest with `asyncio_mode = "auto"`, so `@pytest.mark.asyncio` is not needed. They also use `pretend`,
  `parameterized` and `unittest.mock`, and never access GitHub. Model tests derive from `ModelTest`
  (`tests/models/__init__.py`), with JSON fixtures in `tests/models/resources/`. Tests that run the whole chain from
  diff to HTTP calls are in `tests/providers/github/integration/` (see its `README.md`).
- Commit messages use conventional prefixes (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, with an optional scope).
  Keep the body short: what changed and why, not how you got there. Pull requests follow
  `.github/pull_request_template.md` (see the `pr-description` skill).
- Every commit is signed (`-S`) and signed off (`-s`), with the e-mail registered for the Eclipse Contributor
  Agreement (`docs/developing_otterdog/index.md`). Do not bypass signing; if it fails (no key or agent available in a
  sandbox), stop and tell the user.
- A commit written with an AI agent carries the trailer `Assisted-by: <AGENT_NAME>:<MODEL_VERSION>`, for example
  `Assisted-by: Claude:claude-opus-5-5` or `Assisted-by: Codex:gpt-5.4-mini`, and never a `Co-Authored-By` trailer
  for the agent.
- Generated files, which must not be edited by hand:
    - `.github/workflows/*.lock.yml` are compiled from the `.md` file next to them with `gh aw compile`.
    - `otterdog/webapp/home/playground-examples.json` and `playground-reference.json` are regenerated with
      `make playground-examples`.
- Committers update `CHANGELOG.md` when they prepare a release (`docs/developing_otterdog/release_process.md`).
  Breaking changes are listed under `## [Unreleased]` with their migration path.

## Commands

| Purpose                                                       | Command                                                    |
|---------------------------------------------------------------|------------------------------------------------------------|
| Set up the environment (`.venv`, Playwright Firefox, link `~/.local/bin/otterdog`) | `make init`                           |
| Lint, format and type-check all files                         | `make check` (`poetry run prek -a`)                        |
| Same, on selected files                                       | `poetry run prek run --files <files>`                      |
| Full test suite, in parallel, with coverage                   | `make test`                                                |
| Selected tests                                                | `poetry run pytest <test files> [-k <expression>]`         |
| Tests on Python 3.11 to 3.14 (`[tool.tox]`)                   | `poetry run tox`                                           |
| Webapp assets and JavaScript tests                            | `cd otterdog/webapp/static && npm ci && npm run build && npm test` |
| Build the documentation (strict)                              | `make docs`                                                |
| Serve the documentation locally                               | `make docs-serve`                                          |
| Regenerate the Playground catalogs from the docs              | `make playground-examples`                                 |

CI (`.github/workflows/build.yml`) runs pytest on Python 3.11 to 3.14 (`pytest -ra -n auto --dist worksteal tests`),
with the Playground end-to-end tests in Firefox on 3.14 only. It also builds the webapp assets and runs `npm test`,
runs `prek run --all-files`, and builds the Docker image.

## Choosing the checks for a change

Run the narrowest checks that cover the change, broaden them when shared code is touched, and report which checks
ran and which did not (the pull request template asks for it).

- **Any Python change**: run `poetry run prek run --files <changed files>`, then the tests of the area: the matching
  `tests/models/test_<model>.py`, `tests/operations/`, `tests/providers/github/`, or `tests/webapp/`.
- **Shared code**: `otterdog/models/__init__.py`, `github_organization.py`, `operations/diff_operation.py`,
  `utils.py`, `jsonnet.py` or `providers/github/rest/requester.py` all need `make test`.
- **Default template or schemas**: run `tests/models/`, `tests/schemas/`, `tests/test_packaged_defaults.py` and
  `tests/test_docs_examples.py`.
- **Documentation**: run `make docs`. If reference tables, "Jsonnet Function" sections or guide examples changed,
  first run `make playground-examples`, then `tests/test_docs_examples.py` and `tests/test_docs_playground.py`.
- **Webapp front-end** (`otterdog/webapp/static/src/`): run `npm test` and `npm run build`. The end-to-end tests
  (`poetry run pytest tests/webapp/playground`) are skipped unless the assets are built and Firefox is installed.
- **Workflows** (`.github/workflows/`): pin every `uses:` to a full commit SHA with a trailing `# vX.Y.Z` comment
  (Dependabot maintains both; the exceptions are policies in `.github/zizmor.yml`), set `persist-credentials: false`
  on every `actions/checkout`, and pass `${{ }}` expressions to `run:` through `env:`, never inline. Then run
  `poetry run prek run --files <file>` (zizmor, check-yaml).
- **Agent instructions only** (`AGENTS.md`, `CLAUDE.md`, `.agents/`, `.claude/`): no test suite is relevant. Check
  the paths and the symlinks, and run `poetry run prek run --files <files>`.

## Before opening a pull request

Before you open a pull request, or prepare its final commits and description, the whole branch needs a review with
the `adversarial-review` skill. Reuse a review only when it covers the exact diff, with the same base; otherwise run
one. This is a gate, not a formality:

- The review tries to disprove the assumptions of the change, not to show that it works. Zero findings is a valid
  outcome; passing tests alone are not a conclusion.
- It is read-only by default and ends with a verdict: `ready`, `blocked` or `inconclusive`, with the reason. Never
  open a pull request while the verdict is `blocked`; a draft description that exposes the blocking findings is
  allowed. With `inconclusive`, tell the user what is missing and let them decide. Fix the confirmed bugs when the
  user asks for a fix pass, then review again.
- Scenarios such as `apply` then `plan` are checked with a simulated provider, never against GitHub.
- Write the description with the `pr-description` skill: the verdict and the open findings go to "Notes for
  reviewers", the checks that ran to "Tests", and no box claims a test that did not happen.

Opening the pull request still needs an explicit request from the user.

## Git

Several agent sessions may work in the same checkout at the same time, each on its own files. A git command that
touches files outside your own changes can destroy their work.

- Commit only the changes you made in this session. Stage them by path (`git add <path>...`), never with
  `git add -A` or `git add .`.
- The index is shared: a plain `git commit` takes everything staged, including the work of another session. Check
  `git status` and `git diff --cached` before committing. If the index holds changes that are not yours, leave them
  staged and commit only your paths (`git commit -- <path>...`), or work in a separate `git worktree`.
- A file that also holds changes that are not yours cannot be committed whole: ask the user, or move your work to a
  separate worktree.
- Never run `git reset --hard`, `git checkout .`, `git restore .`, `git clean` (any form, `-X` included),
  `git stash`, `git commit --no-verify`, or `make clean`: it runs `git clean -X -d -f`, which deletes every
  git-ignored file, credentials and local configuration included (`otterdog.json`, `.env`, `*.pem`, `orgs/`).
- If a rebase conflicts, resolve only the files you changed. For any other file, abort and ask the user.
- Never force push unless the user explicitly asks for it.

## Commands that use real GitHub organizations

The tests never access GitHub. The commands below need an `otterdog.json` and real credentials
(`docs/operating_otterdog/setup.md`), and may act on production organizations. A request from the user that names
the command and the organization authorizes that run. It does not extend to other organizations, nor to `--force`
or `--delete-resources` unless the request names them too.

- **Remote mutations: never run one unless the user explicitly asks for that command on that organization.** They
  are `apply`, `local-apply`, `push-config`, `open-pr`, `delete-file`, `dispatch-workflow`, `sync-template`,
  `install-app`, `uninstall-app`, `review-permissions --grant` and `approve-blueprints`. Never add `--force`, which
  skips the interactive approval, or `--delete-resources` on your own initiative.
- **Local writes**: `import` and `fetch-config` read GitHub and overwrite the configuration file of the
  organization; `check-status --json <file>` writes a file; `show --markdown` writes Markdown files into
  `--output-dir`, which defaults to `docs/` of the checkout; `install-deps` installs Firefox for Playwright. Ask
  before running them, and check first that the files they write hold no uncommitted work.
- **GitHub reads**: `plan`, `local-plan`, `check-status`, `show-live`, `validate`, `review-permissions` without
  `--grant`, `list-members`, `list-apps`, `list-advisories` and `check-token-permissions` change no configuration,
  but use real credentials and consume rate limit. `list-blueprints` calls the otterdog webapp instead, and
  `list-projects` only reads `otterdog.json`. Ask before running any of them.
- **Web UI login**: `show-live`, `import`, `plan`, `check-status`, `apply` and `local-apply` log in to the GitHub
  web UI with the bot account, unless web UI settings are skipped (`--no-web-ui`, or the `no_web_ui` default of
  `otterdog.json`); `review-permissions`, `web-login` and `list-advisories --use-web` always do. A web UI login may
  complete a 2FA checkup that GitHub requests.
- The output of `plan` does not guarantee what `apply` will do: `apply` computes the diff again when it runs.
- Do live testing only on a dedicated test organization (`docs/developing_otterdog/testing.md`). Behaviour depends
  on the GitHub plan (Free, Team or Enterprise Cloud).
- Never print, copy or commit credentials or local configuration: `.env`, `*.pem`, `otterdog.json`, `values*.yaml`,
  `orgs/`. They are git-ignored, but they may exist in the working copy with real data.
- **Development targets**: ask before running them.
    - `make dev-webapp*` deploy only to the `minikube` kubectl context (`make check-kube-context`), but with the
      GitHub App configured in your `values.yaml`, which can act on the organizations where it is installed.
    - `make clean-webapp` deletes the minikube cluster and removes devices from the Tailscale tailnet through its API
      (`dev/scripts/remove-ts-machines.sh`).
    - `make init` sets the global Poetry option `virtualenvs.in-project` and overwrites the link
      `~/.local/bin/otterdog`.
- Do not push, open or update pull requests, or post comments or reviews on GitHub without an explicit request.

## Skills

Task-specific procedures are stored as [Agent Skills](https://agentskills.io) in `.agents/skills/<name>/SKILL.md`.
Read the matching skill before you start:

| Skill                    | Use it when                                                                                   |
|--------------------------|-----------------------------------------------------------------------------------------------|
| `github-config-property` | adding or changing a setting of a GitHub resource managed by otterdog (model, default, live state, diff, apply, schema, tests, docs) |
| `github-resource-type`   | adding a new GitHub resource type, a collection with its own identity and lifecycle (organization or repository level) |
| `otterdog-operation`     | adding or changing an operation in `otterdog/operations/` and its command in `otterdog/cli.py` |
| `adversarial-review`     | reviewing the changes of a branch critically before a pull request, or when asked for a self-review |
| `pr-description`         | writing or updating the description of a pull request from its template                      |
| `pr-review-feedback`     | triaging, answering or addressing the review comments of a pull request                       |

`.agents/skills/` is the only source: `.claude/skills/<name>` are relative symlinks to it, for Claude Code. Whether a
tool discovers these files on its own depends on the tool. See `docs/developing_otterdog/ai_agents.md` for how to use
and add skills.
