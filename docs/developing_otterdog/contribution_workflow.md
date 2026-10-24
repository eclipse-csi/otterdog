# Contribution Workflow

This document describes the typical workflow for contributing to Otterdog.

## Getting the source code

### Fork the repository
[Fork](https://docs.github.com/en/get-started/quickstart/fork-a-repo) the [repository](https://github.com/eclipse-csi/otterdog.git)
on GitHub and clone your fork locally.

```bash
git clone https://github.com/<your username>/otterdog.git
cd otterdog
```

### Add a git remote

Add a [remote](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/configuring-a-remote-for-a-fork)
and regularly [sync](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/syncing-a-fork)
to make sure you stay up-to-date with our repository:

```bash
git remote add upstream https://github.com/eclipse-csi/otterdog
git checkout main
git fetch upstream
git merge upstream/main
```

## Prepare development environment

Install otterdog development Python dependencies
```bash
make init
```

See [Development Setup](development_setup.md) for more details.

### Pre-commit hooks

The project extensively uses `pre-commit` hooks to ensure consistent source code formatting and type checking.
To enable `pre-commit` run the following:

```bash
poetry run prek install
```

## Check out a new branch and make your changes

Create a new branch for your changes.

```bash
# Checkout a new branch and make your changes
git checkout -b my-new-feature-branch
# Make your changes...
```

## Run tests

Run tests locally to make sure everything is working as expected.

```bash
# Run tests
make test
```

Note: Code coverage HTML is also available in `htmlcov/`

The end-to-end tests of the Playground of the dashboard, in `tests/webapp/playground/`, run in Firefox with
Playwright. They are skipped unless the assets of the webapp are built and Firefox is installed, which `make init`
does:

```bash
(cd otterdog/webapp/static && npm ci && npm run build)
poetry run pytest tests/webapp/playground
```

The scripts of the Playground also have unit tests, run with `npm test` in `otterdog/webapp/static`.

## Write docs

Otterdog docs are built with [`mkdocs`](https://www.mkdocs.org/) and
[`material`](https://squidfunk.github.io/mkdocs-material/). Check out their docs
for specific Markdown flavors.

Relevant sources are:

* `docs/`: Site contents
* `mkdocs.yml`: Site config
* `.readthedocs.yaml`: Deployment config

Please always review your changes locally (some things render
differently, than you might be used from GitHub):

```bash
make docs-serve
```

Complete jsonnet examples, i.e. examples that define an organization with `orgs.newOrg` without omitting content
with `...` or using placeholders like `<github-id>`, get a link that opens them in the Playground of an otterdog
dashboard. The link is added by the hook `docs/hooks/playground.py`, the url of the dashboard is set by the
environment variable `OTTERDOG_URL` (`https://otterdog.eclipse.org` by default, an empty value omits the links):

```bash
OTTERDOG_URL=https://otterdog.example.org make docs-serve
```

To target the webapp of your development environment, use `make docs-serve-dev`, `make docs-serve-tunnel` or
`make docs-serve-ngrok`, see [Test the Playground with the documentation](testing.md#optional-test-the-playground-with-the-documentation).

The jsonnet examples of the [Configuration Guides](../userguide/guides/index.md) must be complete: the test
`tests/test_docs_examples.py` validates each of them against the example default configuration.

The Playground of the dashboard lists these examples from a catalog generated from the guides, and describes the
properties that it completes from a catalog generated from the [Reference](../reference/index.md), i.e. from the
property tables of its pages and from their "Jsonnet Function" sections. After changing an example or the reference,
update both catalogs, otherwise `tests/test_docs_playground_hook.py` fails:

```bash
make playground-examples
```


## Commit and push your changes

Commit your changes, push your branch to GitHub, and create a pull request.

Please follow the pull request template and fill in as much information as possible. Link to any relevant issues and include a description of your changes.

When your pull request is ready for review, add a comment with the message "please review" and we'll take a look as soon as we can.


### Pull Requests

It should be extremely simple to get started and create a Pull Request.

Unless your change is trivial (typo, docs tweak etc.), please create an issue to discuss the change before
creating a pull request.

If you're looking for something to get your teeth into, check out the
["help wanted"](https://github.com/eclipse-csi/otterdog/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22help%20wanted%22)
label on GitHub.

To make contributing as easy and fast as possible, you'll want to run tests and linting locally. Luckily,
Otterdog has few dependencies, doesn't require compiling and tests don't need access to databases, etc.
Because of this, setting up and running the tests should be very simple.
