#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The pages of a project and of its repositories link to its playground, the menu to the reference guide."""

import shutil
from pathlib import Path
from unittest import mock

import pretend
import pytest

from otterdog.utils import jsonnet_evaluate_file
from otterdog.webapp.db import service
from otterdog.webapp.home import routes

_TEMPLATE_DIR = Path(__file__).parents[2] / "otterdog" / "resources" / "defaults"
_CONFIGURATION = """local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';

orgs.newOrg('my-project', 'my-org') {
  _repositories+:: [orgs.newRepo('my-repo')],
}
"""


@pytest.fixture
def project(tmp_path, monkeypatch):
    shutil.copytree(_TEMPLATE_DIR, tmp_path / "vendor" / "otterdog-defaults")
    (tmp_path / "my-org.jsonnet").write_text(_CONFIGURATION)
    config = pretend.stub(
        github_id="my-org",
        project_name="my-project",
        config=jsonnet_evaluate_file(str(tmp_path / "my-org.jsonnet"), str(tmp_path)),
    )
    installation = pretend.stub(
        base_template="https://github.com/example/otterdog-defaults#otterdog-defaults.libsonnet@v1"
    )
    nothing = mock.AsyncMock(return_value=[])

    monkeypatch.setattr(routes, "get_configuration_by_project_name", mock.AsyncMock(return_value=config))
    monkeypatch.setattr(routes, "get_installation_by_project_name", mock.AsyncMock(return_value=installation))
    monkeypatch.setattr(routes, "get_project_navigation", mock.AsyncMock(return_value={}))
    monkeypatch.setattr(routes, "get_project_base_url", lambda: "http://localhost/projects/")
    monkeypatch.setattr(service, "get_policies", nothing)
    for name in ["get_policies_status", "get_blueprints", "get_blueprints_status", "get_scorecard_results"]:
        monkeypatch.setattr(routes, name, nothing)
    monkeypatch.setattr(routes, "find_scorecard_result", mock.AsyncMock(return_value=None))


async def test_the_page_of_a_project_links_to_its_playground(app, project):
    async with app.test_request_context("/projects/my-project"):
        page = await routes.project("my-project")

    assert 'href="/projects/my-project/playground" class="btn btn-sm btn-primary"' in page
    assert 'href="/projects/my-project/defaults" class="btn btn-sm btn-outline-secondary"' in page
    # each repository is edited in the playground, which shows it
    assert 'href="/projects/my-project/playground?repository=my-repo"' in page
    assert '<h3 class="card-title">Help</h3>' not in page


async def test_the_page_of_a_repository_links_to_the_playground_of_its_project(app, project):
    async with app.test_request_context("/projects/my-project/repos/my-repo"):
        page = await routes.repository("my-project", "my-repo")

    assert 'href="/projects/my-project/playground?repository=my-repo"' in page
    assert "Edit in Playground" in page


async def test_the_menu_links_to_the_reference_guide(app, project):
    async with app.test_request_context("/projects/my-project"):
        page = await routes.project("my-project")

    assert f'href="{app.config["DOCUMENTATION_URL"]}reference/"' in page
    assert "Reference guide" in page
