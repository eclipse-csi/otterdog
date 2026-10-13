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


def _get_config_file(filename: str) -> str:
    import os

    dirname = os.path.dirname(__file__)
    return os.path.join(dirname, filename)
