#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""The cards of the organizations of the projects pages, built from what the dashboard stores about them."""

from datetime import UTC, datetime, timedelta

import pretend
import pytest

from otterdog.webapp.db.models import (
    ApplyStatus,
    ConfigurationModel,
    InstallationModel,
    InstallationStatus,
    PullRequestStatus,
    StatisticsModel,
    TaskModel,
    TaskStatus,
)
from otterdog.webapp.home import projects

_BASE_TEMPLATE = "https://github.com/EclipseFdn/otterdog-defaults#otterdog-defaults.libsonnet@v0.15.0"
_NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


def _installation(project_name="ecd.che", github_id="eclipse-che", status=InstallationStatus.INSTALLED):
    return InstallationModel(
        github_id=github_id, project_name=project_name, installation_status=status, base_template=_BASE_TEMPLATE
    )


def _configuration(github_id="eclipse-che", two_factor=True, permissions="read", repositories=None):
    settings = {
        "two_factor_requirement": two_factor,
        "web_commit_signoff_required": True,
        "default_repository_permission": "read",
        "plan": "free",
        "workflows": {"default_workflow_permissions": permissions},
    }
    if repositories is None:
        repositories = [{"name": "che"}, {"name": "che-docs"}, {"name": "old", "archived": True}]
    config = {"settings": settings, "repositories": repositories}
    return ConfigurationModel(github_id=github_id, project_name=None, config=config, sha="1")


def _statistics(github_id="eclipse-che", **counts):
    values = {
        "two_factor_enforced": 1,
        "total_repos": 11,
        "archived_repos": 1,
        "repos_with_secret_scanning": 2,
        "repos_with_secret_scanning_push_protection": 7,
        "repos_with_branch_protection": 4,
        "repos_with_dependabot_alerts": 5,
        "repos_with_dependabot_security_updates": 0,
        "repos_with_private_vulnerability_reporting": 0,
        "repos_with_code_scanning": 10,
    }
    values.update(counts)
    return StatisticsModel(project_name="ecd.che", github_id=github_id, **values)


def _pull_request(status=PullRequestStatus.OPEN, org_id="eclipse-che", **fields):
    values = {"requires_manual_apply": False, "in_sync": True, "apply_status": ApplyStatus.NOT_APPLIED}
    values.update(fields)
    return pretend.stub(id=pretend.stub(org_id=org_id), status=status, **values)


def _task(status=TaskStatus.FINISHED, log=None, hours=2):
    return TaskModel(
        type=projects.FETCH_CONFIG_TASK,
        org_id="eclipse-che",
        repo_name=".eclipsefdn",
        status=status,
        log=log,
        updated_at=_NOW - timedelta(hours=hours),
    )


def _card(configuration=None, statistics=None, pull_requests=(), task=None, blueprints=None, scorecard=None, **kw):
    return projects.project_card(
        _installation(**kw), configuration, statistics, list(pull_requests), task, blueprints or {}, scorecard
    )


@pytest.mark.parametrize(
    ("base_template", "version"),
    [
        (_BASE_TEMPLATE, "v0.15.0"),
        ("https://github.com/example/defaults#nested/otterdog-defaults.libsonnet@main", "main"),
        ("https://github.com/example/defaults#otterdog-defaults.libsonnet", None),
        (None, None),
    ],
)
def test_the_version_of_the_default_configuration(base_template, version):
    assert projects.defaults_version(base_template) == version


@pytest.mark.parametrize(
    ("delta", "text"),
    [
        (timedelta(seconds=20), "just now"),
        (timedelta(minutes=5), "5 min ago"),
        (timedelta(hours=3, minutes=59), "3 h ago"),
        (timedelta(days=2, hours=1), "2 d ago"),
    ],
)
def test_how_long_ago_a_date_was(delta, text):
    assert projects.ago(_NOW - delta, _NOW) == text
    # the dates of the database are in UTC without time zone
    assert projects.ago((_NOW - delta).replace(tzinfo=None), _NOW) == text


def test_an_organization_with_its_configuration_opens_its_project():
    card = _card(_configuration(), _statistics(), task=_task())

    assert card.state == "configured"
    assert card.linked
    assert card.group == "ecd"
    assert card.defaults_version == "v0.15.0"
    assert (card.two_factor, card.workflow_permissions, card.signoff, card.default_permission, card.plan) == (
        True,
        "read",
        True,
        "read",
        "free",
    )
    assert (card.repositories, card.archived) == (3, 1)
    assert card.attention == ()


def test_the_shares_of_the_active_repositories_with_each_protection():
    card = _card(_configuration(), _statistics())

    # 10 active repositories: secret scanning with or without push protection, Dependabot alerts or updates
    assert [(share.label, share.percentage, share.status) for share in card.shares] == [
        ("Branch protection", 40.0, "critical"),
        ("Secret scanning", 90.0, "good"),
        ("Dependabot", 50.0, "warning"),
        ("Code scanning", 100.0, "good"),
    ]
    assert card.security == 70.0


def test_the_shares_of_an_organization_without_active_repositories_are_unknown():
    card = _card(_configuration(), _statistics(total_repos=2, archived_repos=2))

    assert [share.status for share in card.shares] == ["unknown"] * 4
    assert card.security is None


def test_an_organization_installed_without_configuration_is_to_look_at():
    card = _card(task=_task(TaskStatus.FAILED, log="failed to evaluate"))

    assert card.state == "unconfigured"
    assert not card.linked
    assert card.repositories is None
    assert card.fetch == projects.Fetch(True, _NOW - timedelta(hours=2), "failed to evaluate")
    assert [x.key for x in card.attention] == ["unconfigured", "fetch"]


def test_an_organization_not_installed_has_nothing_to_look_at():
    card = _card(_configuration(two_factor=False), status=InstallationStatus.NOT_INSTALLED)

    assert card.state == "inactive"
    assert not card.linked
    assert card.attention == ()


def test_the_reasons_to_look_at_an_organization():
    pull_requests = [
        _pull_request(),
        _pull_request(requires_manual_apply=True),
        _pull_request(in_sync=False),
        _pull_request(PullRequestStatus.MERGED, apply_status=ApplyStatus.FAILED),
        _pull_request(PullRequestStatus.MERGED, apply_status=ApplyStatus.COMPLETED),
    ]
    card = _card(
        _configuration(two_factor=False, permissions="write"),
        pull_requests=pull_requests,
        task=_task(),
        blueprints={"failure": 2, "success": 5},
        scorecard=6.4,
    )

    assert card.open_pull_requests == 3
    assert card.pull_requests_to_look_at == 3
    assert card.failing_blueprints == 2
    assert card.scorecard == 6.4
    assert [(x.key, x.label) for x in card.attention] == [
        ("two-factor", "2FA not enforced"),
        ("write", "Write workflow permissions"),
        ("blueprints", "2 failing blueprints"),
        ("pull-requests", "3 pull requests to look at"),
    ]


def test_the_cards_take_the_data_of_their_organization_and_are_grouped():
    installations = [
        _installation("technology.csi", "eclipse-csi"),
        _installation("ecd.theia", "eclipse-theia"),
        _installation("ecd.che", "eclipse-che", InstallationStatus.NOT_INSTALLED),
    ]
    cards = projects.project_cards(
        installations,
        {"eclipse-csi": _configuration("eclipse-csi")},
        {"eclipse-csi": _statistics("eclipse-csi")},
        [_pull_request(org_id="eclipse-csi"), _pull_request(org_id="eclipse-theia", requires_manual_apply=True)],
        {},
        {"eclipse-theia": {"failure": 1}},
        {"eclipse-csi": 7.5},
    )

    assert [card.project_name for card in cards] == ["ecd.che", "ecd.theia", "technology.csi"]
    csi = cards[2]
    assert (csi.state, csi.open_pull_requests, csi.scorecard, csi.security) == ("configured", 1, 7.5, 70.0)
    theia = cards[1]
    assert [x.key for x in theia.attention] == ["unconfigured", "blueprints", "pull-requests"]

    assert [(group, [card.project_name for card in members]) for group, members in projects.group_cards(cards)] == [
        ("ecd", ["ecd.che", "ecd.theia"]),
        ("technology", ["technology.csi"]),
    ]
    assert projects.summary(cards) == {"configured": 1, "unconfigured": 1, "inactive": 1, "attention": 1}
