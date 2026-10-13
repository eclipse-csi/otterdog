#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio

import pytest

from otterdog.config import OtterdogConfig
from otterdog.webapp import mongo
from otterdog.webapp.db.models import InstallationModel


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


async def test_installation_tasks_are_bounded(app):
    from otterdog.webapp.db.service import _execute_installation_task

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
