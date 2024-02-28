#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import re

from motor.motor_asyncio import AsyncIOMotorClient
from odmantic import AIOEngine
from quart import Quart


class Mongo:
    def __init__(self) -> None:
        self._client: AsyncIOMotorClient | None = None
        self._engine: AIOEngine | None = None

    def init_app(self, app: Quart) -> None:
        connection_uri = app.config["MONGO_URI"]

        m = re.match(r"^((mongodb:(?:/{2})?)((\w+?):(\w+?)@|:?@?)(\w+?):(\d+)/)(\w+?)$", connection_uri)

        if m is not None:
            server_uri = m.group(1)
            database = m.group(8)
        else:
            raise RuntimeError(f"failed to parse mongo connection uri: '{connection_uri}'")

        self._client = AsyncIOMotorClient(server_uri)
        self._engine = AIOEngine(client=self._client, database=database)

    @property
    def odm(self) -> AIOEngine:
        assert self._engine is not None
        return self._engine


async def init_mongo_database(mongo: Mongo) -> None:
    from .models import (
        ConfigurationModel,
        InstallationModel,
        PullRequestModel,
        StatisticsModel,
        TaskModel,
    )

    await mongo.odm.configure_database(
        [
            InstallationModel,
            TaskModel,
            ConfigurationModel,
            PullRequestModel,
            StatisticsModel,
        ]  # type: ignore
    )
