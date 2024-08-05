#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pytest

from otterdog.config import OtterdogConfig
from otterdog.webapp import mongo
from otterdog.webapp.db.models import InstallationModel


@pytest.mark.asyncio
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


def _get_config_file(filename: str) -> str:
    import os

    dirname = os.path.dirname(__file__)
    return os.path.join(dirname, filename)
