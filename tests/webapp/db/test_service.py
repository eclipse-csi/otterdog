#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio
from unittest import mock

import pytest

from otterdog.config import OtterdogConfig
from otterdog.webapp import mongo
from otterdog.webapp.db import service
from otterdog.webapp.db.models import InstallationModel, InstallationStatus


@pytest.mark.skip(reason="integration test")
async def test_update_installations(app):
    from otterdog.webapp.db import init_mongo_database
    from otterdog.webapp.db.service import (
        get_all_installations_count,
        get_installations,
        update_installations_from_config,
    )

    async with app.app_context():
        await mongo.odm.get_collection(InstallationModel).drop()
        await init_mongo_database(mongo)

        policies = []

        config = OtterdogConfig.from_file(_get_config_file("config/otterdog.json"), False)
        await update_installations_from_config(config, policies, False)

        assert await get_all_installations_count() == 1
        assert (await get_installations())[0].github_id == "OtterdogTest"

        config2 = OtterdogConfig.from_file(_get_config_file("config/otterdog_modified.json"), False)
        await update_installations_from_config(config2, policies, False)

        assert await get_all_installations_count() == 1
        assert (await get_installations())[0].github_id == "OtterdogTest2"


def _installation(github_id: str) -> InstallationModel:
    return InstallationModel(  # type: ignore
        github_id=github_id,
        project_name=f"project-{github_id}",
        installation_id=1,
        installation_status=InstallationStatus.INSTALLED,
        config_repo=".eclipsefdn",
    )


@pytest.fixture
def refreshed_installations(monkeypatch) -> list[str]:
    """
    Records the installations whose data update_app_installations refreshes, out of
    'configured', whose configuration is already stored, and 'unconfigured'.
    """

    refreshed: list[str] = []

    async def update_data_for_installation(installation: InstallationModel) -> None:
        refreshed.append(installation.github_id)

    async def get_configuration_by_github_id(github_id: str):
        return None if github_id == "unconfigured" else mock.MagicMock()

    rest_api = mock.MagicMock()
    rest_api.app.get_app_installations = mock.AsyncMock(return_value=[])

    monkeypatch.setattr(service, "mongo", mock.MagicMock())
    monkeypatch.setattr(service, "get_rest_api_for_app", lambda: rest_api)
    monkeypatch.setattr(
        service,
        "get_active_installations",
        mock.AsyncMock(return_value=[_installation("configured"), _installation("unconfigured")]),
    )
    monkeypatch.setattr(service, "get_configuration_by_github_id", get_configuration_by_github_id)
    monkeypatch.setattr(service, "update_data_for_installation", update_data_for_installation)
    monkeypatch.setattr(service, "update_policies_and_blueprints_for_installation", mock.AsyncMock())

    return refreshed


async def test_update_app_installations_refreshes_installations_without_configuration(refreshed_installations):
    await service.update_app_installations([], [])

    assert refreshed_installations == ["unconfigured"]


async def test_update_app_installations_refreshes_installations_to_force_update(refreshed_installations):
    await service.update_app_installations([], [], {"project-configured"})

    assert refreshed_installations == ["configured", "unconfigured"]


async def test_update_app_installations_refreshes_every_installation_once_when_forced(refreshed_installations):
    await service.update_app_installations([], [], force_update_data=True)

    assert refreshed_installations == ["configured", "unconfigured"]


class _AddedInstallation:
    """The stubs add_app_installation relies on, for an app installation of org 'new-org'."""

    def __init__(self, monkeypatch, stored: dict[str, InstallationModel], configured: dict[str, str]):
        """
        :param stored: the installations stored when the app is installed, by github id
        :param configured: the orgs that the latest otterdog config defines, github id by project name
        """

        self.stored = stored
        self.saved: list[InstallationModel] = []
        self.deleted: list[InstallationModel] = []
        self.refreshed: list[str] = []
        # the operations on the database and the fetching of data, in their order
        self.operations: list[str] = []

        rest_api = mock.MagicMock()
        rest_api.app.get_app_installation = mock.AsyncMock(
            return_value={"id": 178172786, "account": {"login": "new-org"}, "suspended_at": None}
        )

        otterdog_config = OtterdogConfig.from_dict(
            {
                "defaults": {"jsonnet": {"base_template": "https://github.com/org/repo#base.libsonnet@main"}},
                "organizations": [{"name": name, "github_id": github_id} for name, github_id in configured.items()],
            },
            False,
            ".",
        )

        async def get_installation_by_github_id(github_id: str):
            return self.stored.get(github_id)

        async def get_installation_by_project_name(project_name: str):
            return next((x for x in self.stored.values() if x.project_name == project_name), None)

        async def save(model: InstallationModel) -> None:
            self.saved.append(model)
            self.operations.append(f"save {model.github_id}")

        async def delete(model: InstallationModel) -> None:
            self.deleted.append(model)
            self.operations.append(f"delete {model.github_id}")

        async def cleanup_data() -> None:
            self.operations.append("cleanup")

        async def update_data_for_installation(installation: InstallationModel) -> None:
            self.refreshed.append(installation.github_id)
            self.operations.append(f"fetch {installation.github_id}")

        self.refresh_otterdog_config = mock.AsyncMock(return_value=otterdog_config)
        # the other changes of the otterdog config are left to the processing of the push that made them
        self.update_installations_from_config = mock.AsyncMock()

        monkeypatch.setattr(service, "mongo", mock.MagicMock(odm=mock.MagicMock(save=save, delete=delete)))
        monkeypatch.setattr(service, "get_rest_api_for_app", lambda: rest_api)
        monkeypatch.setattr(service, "get_installation_by_github_id", get_installation_by_github_id)
        monkeypatch.setattr(service, "get_installation_by_project_name", get_installation_by_project_name)
        monkeypatch.setattr(service, "refresh_otterdog_config", self.refresh_otterdog_config)
        monkeypatch.setattr(service, "update_installations_from_config", self.update_installations_from_config)
        monkeypatch.setattr(service, "cleanup_data", cleanup_data)
        monkeypatch.setattr(service, "update_data_for_installation", update_data_for_installation)
        monkeypatch.setattr(service, "update_policies_and_blueprints_for_installation", mock.AsyncMock())

    def saved_installations(self) -> list[tuple]:
        return [(x.github_id, x.project_name, x.installation_id, x.installation_status) for x in self.saved]


def _not_installed(github_id: str) -> InstallationModel:
    model = _installation(github_id)
    model.installation_id = 0
    model.installation_status = InstallationStatus.NOT_INSTALLED
    return model


async def test_add_app_installation_of_known_org(monkeypatch):
    added = _AddedInstallation(monkeypatch, stored={"new-org": _not_installed("new-org")}, configured={})

    await service.add_app_installation(178172786, [], [])

    assert added.saved_installations() == [("new-org", "project-new-org", 178172786, InstallationStatus.INSTALLED)]
    assert added.operations == ["save new-org", "fetch new-org"]
    added.refresh_otterdog_config.assert_not_awaited()


async def test_add_app_installation_reloads_otterdog_config_for_unknown_org(monkeypatch, caplog):
    # the app has been installed before the push adding the org to the otterdog config has been processed
    added = _AddedInstallation(
        monkeypatch,
        stored={"other-org": _installation("other-org")},
        configured={"project-other-org": "other-org", "technology.new": "new-org"},
    )

    with caplog.at_level("WARNING", logger=service.logger.name):
        await service.add_app_installation(178172786, [], [])

    added.refresh_otterdog_config.assert_awaited_once()
    assert added.saved_installations() == [("new-org", "technology.new", 178172786, InstallationStatus.INSTALLED)]
    assert added.deleted == []
    assert added.refreshed == ["new-org"]
    # the other orgs are left to the processing of the push that changed the otterdog config
    added.update_installations_from_config.assert_not_awaited()
    assert "org 'new-org' (installation id '178172786') that is not known yet" in caplog.text


async def test_add_app_installation_replaces_installation_of_project_whose_org_has_changed(monkeypatch):
    previous = _installation("previous-org")
    previous.project_name = "technology.new"
    added = _AddedInstallation(monkeypatch, stored={"previous-org": previous}, configured={"technology.new": "new-org"})

    await service.add_app_installation(178172786, [], [])

    assert added.deleted == [previous]
    assert added.saved_installations() == [("new-org", "technology.new", 178172786, InstallationStatus.INSTALLED)]
    # the data of the previous org, e.g. its configuration, holds the project name which is unique
    assert added.operations == ["delete previous-org", "save new-org", "cleanup", "fetch new-org"]


@pytest.mark.parametrize(
    "configured",
    [
        pytest.param({}, id="not defined"),
        pytest.param({"technology.new": "New-Org"}, id="defined with another case"),
    ],
)
async def test_add_app_installation_ignores_org_not_defined_in_otterdog_config(monkeypatch, caplog, configured):
    added = _AddedInstallation(monkeypatch, stored={}, configured=configured)

    with caplog.at_level("WARNING", logger=service.logger.name):
        await service.add_app_installation(178172786, [], [])

    added.refresh_otterdog_config.assert_awaited_once()
    assert added.saved == []
    assert added.refreshed == []
    assert "org 'new-org' (installation id '178172786') that the otterdog config does not define" in caplog.text


async def test_installation_tasks_are_scheduled_through_the_bound(app, monkeypatch):
    from otterdog.webapp.tasks.fetch_all_pull_requests import FetchAllPullRequestsTask
    from otterdog.webapp.tasks.fetch_blueprints import FetchBlueprintsTask
    from otterdog.webapp.tasks.fetch_config import FetchConfigTask
    from otterdog.webapp.tasks.fetch_policies import FetchPoliciesTask

    scheduled = []
    monkeypatch.setattr(app, "add_background_task", lambda func, *args: scheduled.append((func, *args)))

    async with app.app_context():
        installation = _installation("org")
        await service.update_data_for_installation(installation)
        await service.update_policies_and_blueprints_for_installation(installation, [], [])

    assert all(func is service._execute_installation_task for func, _ in scheduled)
    assert [type(task) for _, task in scheduled] == [
        FetchConfigTask,
        FetchAllPullRequestsTask,
        FetchPoliciesTask,
        FetchBlueprintsTask,
    ]


async def test_installation_tasks_are_bounded(app):
    from otterdog.webapp.db.service import _execute_installation_task

    assert app.config["MAX_CONCURRENT_INSTALLATION_TASKS"] >= 1

    max_concurrent_tasks = 3
    app.config["MAX_CONCURRENT_INSTALLATION_TASKS"] = max_concurrent_tasks

    running = 0
    max_running = 0

    class _Task:
        async def execute(self) -> None:
            nonlocal running, max_running
            running += 1
            max_running = max(max_running, running)
            await asyncio.sleep(0.01)
            running -= 1

    async with app.app_context():
        await asyncio.gather(*[_execute_installation_task(_Task()) for _ in range(3 * max_concurrent_tasks)])

    assert max_running == max_concurrent_tasks


def _required_file_blueprint(description: str, content: str):
    from otterdog.webapp.blueprints import create_blueprint

    return create_blueprint(
        "required_file",
        "require-dependabot",
        "otterdog/blueprints/require_dependabot.yml",
        "Require Dependabot",
        description,
        {"files": [{"path": ".github/dependabot.yml", "content": content, "strict": True}]},
    )


@pytest.fixture
def stored_blueprint(monkeypatch):
    """
    The stored model of a blueprint, which update_or_create_blueprint looks up and saves in place.
    """

    from otterdog.webapp.db.models import BlueprintId, BlueprintModel

    blueprint = _required_file_blueprint("old description", "version: 2")
    blueprint_model = BlueprintModel(
        id=BlueprintId(org_id="OtterdogTest", blueprint_type=blueprint.type.value, blueprint_id=blueprint.id),
        path=blueprint.path,
        name=blueprint.name,
        description=blueprint.description,
        recheck_needed=False,
        config=blueprint.config,
    )

    monkeypatch.setattr(service, "find_blueprint", mock.AsyncMock(return_value=blueprint_model))
    monkeypatch.setattr(service, "save_blueprint", mock.AsyncMock())
    return blueprint_model


async def test_update_or_create_blueprint_updates_config_along_with_description(stored_blueprint):
    blueprint = _required_file_blueprint("new description", "version: 2\nupdates: []")

    assert await service.update_or_create_blueprint("OtterdogTest", blueprint) is True
    assert stored_blueprint.description == "new description"
    assert stored_blueprint.config == blueprint.config


async def test_update_or_create_blueprint_keeps_pending_recheck(stored_blueprint):
    stored_blueprint.recheck_needed = True
    blueprint = _required_file_blueprint("old description", "version: 2")

    assert await service.update_or_create_blueprint("OtterdogTest", blueprint) is True
    assert stored_blueprint.recheck_needed is True


def _get_config_file(filename: str) -> str:
    import os

    dirname = os.path.dirname(__file__)
    return os.path.join(dirname, filename)
