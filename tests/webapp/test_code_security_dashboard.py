#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The dashboard shows the code security configurations and the security settings that apply to repositories."""

import shutil
from pathlib import Path
from unittest import mock

import pretend
import pytest
from ariadne import graphql

from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import jsonnet_evaluate_file
from otterdog.webapp.api.graphql import schema
from otterdog.webapp.db import service
from otterdog.webapp.db.service import Statistics
from otterdog.webapp.home import routes
from otterdog.webapp.tasks.fetch_config import get_organization_statistics

_TEMPLATE_DIR = Path(__file__).parents[2] / "otterdog" / "resources" / "defaults"
# 'my-repo' enables Dependabot alerts, which its configuration disables
_CONFIGURATION = """local orgs = import 'vendor/otterdog-defaults/otterdog-defaults.libsonnet';

orgs.newOrg('my-project', 'my-org') {
  code_security_configurations+: [
    orgs.newOrgCodeSecurityConfiguration('baseline') {
      description: "Baseline for all repositories",
      secret_protection: "enabled",
      dependabot_alerts: "disabled",
      secret_scanning: "enabled",
      secret_scanning_push_protection: "enabled",
      private_vulnerability_reporting: "enabled",
      code_scanning_default_setup: "not_set",
    },
  ],
  _repositories+:: [
    orgs.newRepo('my-repo') {
      dependabot_alerts_enabled: true,
      code_security_configuration: "baseline",
    },
    orgs.newRepo('private-repo') {
      private: true,
      code_security_configuration: "baseline",
    },
    orgs.newRepo('other-repo') {
      code_scanning_default_setup_enabled: true,
    },
  ],
}
"""


@pytest.fixture
def config(tmp_path):
    shutil.copytree(_TEMPLATE_DIR, tmp_path / "vendor" / "otterdog-defaults")
    (tmp_path / "my-org.jsonnet").write_text(_CONFIGURATION)
    return pretend.stub(
        github_id="my-org",
        project_name="my-project",
        config=jsonnet_evaluate_file(str(tmp_path / "my-org.jsonnet"), str(tmp_path)),
    )


@pytest.fixture
def project(config, monkeypatch):
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


async def test_the_page_of_a_project_lists_its_code_security_configurations(app, project):
    async with app.test_request_context("/projects/my-project"):
        page = await routes.project("my-project")

    assert 'href="#code-security" role="tab"' in page
    assert "Baseline for all repositories" in page
    # the configuration is referenced by 2 repositories
    assert 'title="my-repo, private-repo"' in page
    assert "1 active repositories without a code security configuration" in page


async def test_the_page_of_a_project_shows_the_settings_set_by_the_configuration(app, project):
    async with app.test_request_context("/projects/my-project"):
        page = await routes.project("my-project")

    assert 'class="tab-link badge text-bg-info text-decoration-none">baseline</a>' in page
    assert "title=\"set by code security configuration 'baseline'\"" in page


async def test_the_page_of_a_project_without_code_security_configurations(app, project, config):
    config.config["code_security_configurations"] = []
    for repo in config.config["repositories"]:
        repo["code_security_configuration"] = None

    async with app.test_request_context("/projects/my-project"):
        page = await routes.project("my-project")

    assert "No code security configuration is defined" in page
    assert "set by code security configuration" not in page


async def test_the_page_of_a_repository_shows_its_effective_security_settings(app, project):
    async with app.test_request_context("/projects/my-project/repos/my-repo"):
        page = await routes.repository("my-project", "my-repo")

    assert '<span class="float-end badge text-bg-info">baseline</span>' in page
    # Dependabot alerts are disabled by the configuration, although the repository enables them
    assert "Dependabot Alerts" in page
    assert '<span class="float-end badge text-bg-danger">False</span>' in page
    assert "title=\"set by code security configuration 'baseline'\"" in page


async def test_the_index_shows_code_scanning_and_code_security_configurations(app, monkeypatch):
    statistics = Statistics(
        total_projects=1,
        total_repos=10,
        archived_repos=2,
        repos_with_code_scanning=3,
        repos_with_code_security_configuration=4,
        private_repos_with_licensed_security_features=1,
    )
    nothing = mock.AsyncMock(return_value=[])
    monkeypatch.setattr(routes, "get_installations", nothing)
    monkeypatch.setattr(routes, "get_configurations", nothing)
    monkeypatch.setattr(routes, "get_statistics", mock.AsyncMock(return_value=statistics))
    monkeypatch.setattr(routes, "get_open_or_incomplete_pull_requests_count", mock.AsyncMock(return_value=0))
    monkeypatch.setattr(routes, "get_merged_pull_requests_count", mock.AsyncMock(return_value=0))
    monkeypatch.setattr(routes, "get_project_navigation", mock.AsyncMock(return_value={}))

    async with app.test_request_context("/index"):
        page = await routes.index()

    assert "37.5% with default setup" in page
    assert "50.0% with a configuration" in page
    assert "1 private repositories with licensed features" in page
    assert "data: [5, 3]," in page


def test_statistics_count_the_settings_set_by_the_configurations(config):
    org = GitHubOrganization.from_model_data(config.config)

    statistics = get_organization_statistics("my-project", "my-org", org)

    assert statistics.total_repos == 3
    assert statistics.repos_with_code_security_configuration == 2
    # only the private repository uses licensed features, Secret Protection being enabled
    assert statistics.private_repos_with_licensed_security_features == 1
    # the configuration disables Dependabot alerts, 'other-repo' keeps the ones of the default repository
    assert statistics.repos_with_dependabot_alerts == 1
    # the configuration enables private vulnerability reporting, the default repository disables it
    assert statistics.repos_with_private_vulnerability_reporting == 2
    # the configuration does not set code scanning, only 'other-repo' enables it
    assert statistics.repos_with_code_scanning == 1


async def test_the_api_exposes_the_code_security_configurations(config, monkeypatch):
    from otterdog.webapp.api import graphql as api

    monkeypatch.setattr(api, "get_configurations", mock.AsyncMock(return_value=[config]))
    query = """
    {
      projects {
        config {
          code_security_configurations { name dependabot_alerts default_for_new_repos }
          repositories { name code_security_configuration }
        }
      }
    }
    """

    success, result = await graphql(schema, {"query": query})

    assert success, result
    project_config = result["data"]["projects"][0]["config"]
    assert project_config["code_security_configurations"] == [
        {"name": "baseline", "dependabot_alerts": "disabled", "default_for_new_repos": "none"}
    ]
    assert {"name": "my-repo", "code_security_configuration": "baseline"} in project_config["repositories"]
    assert {"name": "other-repo", "code_security_configuration": None} in project_config["repositories"]
