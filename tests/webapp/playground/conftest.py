#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""
Browser-test setup: render playground pages once, then serve them as static HTML.

Python uses the real route/template rendering to embed the library contents in each
page. A local HTTP server serves those snapshots and the built webapp assets.
Firefox runs the real editor and Jsonnet WASM evaluator; evaluation is not mocked.
The custom-template pages replace only the GitHub checkout with local fixture files.

Tests are skipped if assets are missing (`npm run build` in otterdog/webapp/static)
or Firefox is unavailable (`python -m playwright install firefox`).
"""

import asyncio
import functools
import http.server
import json
import threading
from pathlib import Path
from typing import ClassVar
from unittest import mock

import pytest
from quart import Quart, render_template, request

from otterdog.config import OrganizationConfig, OtterdogConfig
from otterdog.webapp import create_app
from otterdog.webapp.config import TestingConfig
from otterdog.webapp.home import routes

from .helpers import Playground

_ASSETS_DIR = Path(routes.__file__).parents[1] / "static" / "assets"
_BASE_TEMPLATE = "https://github.com/example/otterdog-defaults#otterdog-defaults.libsonnet@v1.0.0"
_IMPORT = "local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';\n\n"

ORGANIZATION = (
    _IMPORT + "orgs.newOrg('my-project', 'my-org') {\n"
    "  settings+: { name: 'Org from the configuration' },\n"
    "  _repositories+:: [\n"
    "    orgs.newRepo('website') { has_wiki: true,"
    " rulesets: [orgs.newRepoRuleset('tags-protection') { allows_updates: false }] },\n"
    "    orgs.newRepo('api') { rulesets: [orgs.newRepoRuleset('tags-protection') { allows_updates: false }] },\n"
    "  ],\n"
    "}\n"
)

# a large configuration extending the default configuration with its own functions, like many organizations do
LARGE_ORGANIZATION = (
    "local orgsBase = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';\n"
    "local orgs = orgsBase + {\n"
    "  newRepo(name):: orgsBase.newRepo(name) { delete_branch_on_merge: true },\n"
    "};\n\n"
    "orgs.newOrg('large-project', 'large-org') {\n"
    "  settings+: {\n"
    "    web_commit_signoff_required: false,\n"
    "  },\n"
    "  _repositories+:: [\n"
    "    orgs.newRepo('website') { has_wiki: true, web_commit_signoff_required: false },\n"
    + "".join(
        f"    orgs.newRepo('repository-{index}') {{ description: 'Repository {index}' }},\n" for index in range(150)
    )
    + "  ],\n}\n"
)

# the projects of the instance, whose configuration the impact of an edited default configuration is evaluated on
PROJECTS = [
    {
        "name": "alpha",
        "jsonnet": _IMPORT + "orgs.newOrg('alpha', 'alpha-org') {\n  _repositories+:: [orgs.newRepo('website')],\n}\n",
    },
    {
        "name": "beta",
        "jsonnet": _IMPORT
        + "orgs.newOrg('beta', 'beta-org') {\n  _repositories+:: [orgs.newRepo('docs') { has_wiki: false }],\n}\n",
    },
    {
        "name": "broken",
        "jsonnet": _IMPORT + "orgs.newOrg('broken', 'broken-org') {\n  settings+: { name: unknown },\n}\n",
    },
    {
        "name": "gamma",
        "jsonnet": _IMPORT + "orgs.newOrg('gamma', 'gamma-org') {\n"
        "  webhooks+: [orgs.newOrgWebhook('https://example.com/hook')],\n"
        "  _repositories+:: [orgs.newRepo('api') { has_wiki: false }],\n}\n",
    },
    {"name": "pending", "jsonnet": None},
]


class _Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map: ClassVar[dict[str, str]] = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
    }

    def log_message(self, format, *args):
        pass


async def _render_home_template(template_name, **context):
    segments = request.path.strip("/").split("/")
    return await render_template(f"home/{template_name}", segments=segments, projects={}, version="0", **context)


async def _render_pages(directory: Path) -> None:
    app = create_app(TestingConfig)
    example = await routes._example_template()
    assert example is not None
    instance = {**example, "link": routes._default_configuration_link(_BASE_TEMPLATE)}
    config = OtterdogConfig.from_dict(
        {"defaults": {"jsonnet": {"base_template": _BASE_TEMPLATE}}, "organizations": []}, False, "."
    )
    organization = {
        "name": "my-project",
        "jsonnet": ORGANIZATION,
        "url": "https://github.com/my-org/.otterdog/blob/HEAD/otterdog/my-org.jsonnet",
        "edit_url": "https://github.com/my-org/.otterdog/edit/main/otterdog/my-org.jsonnet",
    }
    large = {"name": "large-project", "jsonnet": LARGE_ORGANIZATION, "url": "https://github.com/large-org/.otterdog"}

    with (
        mock.patch.object(routes, "render_home_template", _render_home_template),
        mock.patch.object(routes, "get_otterdog_config", mock.AsyncMock(return_value=config)),
        mock.patch.object(routes, "_instance_template", mock.AsyncMock(return_value=instance)),
        mock.patch.object(routes, "get_temporary_base_directory", return_value=str(directory)),
    ):
        async with app.test_request_context("/playground"):
            (directory / "index.html").write_text(await routes.global_playground())
        async with app.test_request_context("/playground?template=example"):
            (directory / "example.html").write_text(await routes.global_playground())
        async with app.test_request_context("/projects/my-project/playground"):
            (directory / "org.html").write_text(await routes._render_playground(example, "my-project", organization))
        async with app.test_request_context("/projects/large-project/playground"):
            (directory / "large.html").write_text(await routes._render_playground(instance, "large-project", large))
        async with app.test_request_context("/admin/template-impact"):
            (directory / "template-impact.html").write_text(await routes.template_impact())

    await _render_custom_template_pages(app, directory)

    (directory / "admin" / "template-impact").mkdir(parents=True)
    (directory / "admin" / "template-impact" / "configurations").write_text(json.dumps({"projects": PROJECTS}))


async def _render_custom_template_pages(app: Quart, directory: Path) -> None:
    """Render the custom-template pages used by completion and error-link tests.

    The fake template repository contains:
        nested/otterdog-defaults.libsonnet            selected custom template
        nested/otterdog-functions.libsonnet           custom helper
        nested/upstream/otterdog-defaults.libsonnet   library with newRepo(name)
        nested/upstream/otterdog-functions.libsonnet  different helper, same basename

    Four pages define newRepo in different ways, each allowing newRepo() to
    return a repository named 'custom-repo'. The completion tests select this
    call and evaluate the result. The organization name comes from the custom
    helper, letting the snippet tests check which template they are using.

    The fifth page makes the custom helper raise an error. The evaluator reports
    only its filename, which also belongs to the upstream helper. Error navigation
    must leave both helpers unmarked and link only the uniquely identified caller.
    """
    org_config = OrganizationConfig.of(
        project_name="custom",
        github_id="custom",
        config_repo=".otterdog",
        base_template="https://github.com/example/custom#nested/otterdog-defaults.libsonnet@main",
        credential_data={},
        base_dir=str(directory),
        work_dir=str(directory),
    )
    jsonnet_config = org_config.jsonnet_config
    repository_dir = Path(jsonnet_config.template_dir)
    selected_template = repository_dir / "nested" / "otterdog-defaults.libsonnet"
    custom_helper = repository_dir / "nested" / "otterdog-functions.libsonnet"
    upstream_dir = repository_dir / "nested" / "upstream"
    upstream_dir.mkdir(parents=True)
    # Keep the library deliberately small: newRepo exposes the selected name in
    # the output, and newOrg supplies the organization shape expected by the UI.
    (upstream_dir / "otterdog-defaults.libsonnet").write_text(
        """local newRepo(name) = { name: name };
local newOrg(name, id) = {
  project_name: name,
  github_id: id,
  settings: { name: id },
  repositories: [],
};
{ newRepo: newRepo, newOrg: newOrg }
"""
    )
    (upstream_dir / "otterdog-functions.libsonnet").write_text("{ name: 'Upstream helper' }")
    organization = {
        "name": "custom",
        "jsonnet": f"local orgs = {jsonnet_config.import_statement}; orgs.newOrg('custom', 'custom')",
        "url": "https://github.com/custom/.otterdog/blob/HEAD/otterdog/custom.jsonnet",
    }

    # Each expression is a complete Jsonnet object exporting a newRepo function.
    # The library's newRepo(name) needs a name; these custom functions supply one.
    repository_constructors = {
        "custom-local.html": "local newRepo() = upstream.newRepo('custom-repo'); { newRepo: newRepo }",
        "custom-method.html": "{ newRepo(): upstream.newRepo('custom-repo') }",
        "custom-function.html": "{ newRepo: function() upstream.newRepo('custom-repo') }",
        "custom-optional.html": "{ newRepo(name='custom-repo'): upstream.newRepo(name) }",
        "custom-helper-error.html": "{ newRepo(): upstream.newRepo('custom-repo') }",
    }
    # Every rendered page embeds its own copy of the files. Reusing this checkout
    # for the next variant cannot change the pages already written to disk.
    for page_name, constructor in repository_constructors.items():
        selected_template.write_text(
            f"""local upstream = import 'upstream/otterdog-defaults.libsonnet';
local helper = import 'otterdog-functions.libsonnet';
local constructors =
{constructor};
constructors + {{
  newOrg(project, id): upstream.newOrg(project, id) {{
    settings+: {{ name: helper.name }},
  }},
}}
"""
        )
        if page_name == "custom-helper-error.html":
            custom_helper.write_text("error 'custom helper failed'")
        else:
            custom_helper.write_text("{ name: 'Custom helper' }")

        # Use the local checkout above instead of downloading the fake GitHub repo.
        # The real loader still builds the file map consumed by the WASM evaluator.
        with mock.patch.object(jsonnet_config, "_init_base_template", mock.AsyncMock()):
            template = await routes._instance_template(org_config)
        with mock.patch.object(routes, "render_home_template", _render_home_template):
            async with app.test_request_context("/projects/custom/playground"):
                html = await routes._render_playground(template, "custom", organization)
        (directory / page_name).write_text(html)


@pytest.fixture(scope="session")
def playground_url(tmp_path_factory):
    if not (_ASSETS_DIR / "manifest.json").exists():
        pytest.skip("the assets of the webapp are not built, run `npm run build` in otterdog/webapp/static")

    directory = tmp_path_factory.mktemp("playground")
    (directory / "assets").symlink_to(_ASSETS_DIR)
    asyncio.run(_render_pages(directory))

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Handler, directory=str(directory)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as playwright:
        try:
            browser = playwright.firefox.launch()
        except Error as error:
            pytest.skip(f"Firefox is not installed for Playwright, run `python -m playwright install firefox`: {error}")
        yield browser
        browser.close()


@pytest.fixture
def playground(browser, playground_url):
    context = browser.new_context(viewport={"width": 1700, "height": 1000})
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield Playground(page, playground_url)
    context.close()
    assert errors == [], f"javascript errors: {errors}"
