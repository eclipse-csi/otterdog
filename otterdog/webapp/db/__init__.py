#  *******************************************************************************
#  Copyright (c) 2024-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from urllib.parse import urlparse

from motor.motor_asyncio import AsyncIOMotorClient
from odmantic import AIOEngine
from quart import Quart

from otterdog.utils import unwrap


def _parse(mongo_uri: str) -> tuple[str, str]:
    urlparsed = urlparse(mongo_uri)
    if urlparsed.scheme != "mongodb":
        raise RuntimeError(f"invalid mongo connection uri, no scheme: '{mongo_uri}'")

    elif urlparsed.netloc == "" or (urlparsed.path == "" or len(urlparsed.path) < 2):
        raise RuntimeError(f"invalid mongo connection uri, no database: '{mongo_uri}'")

    else:
        server_uri = f"{urlparsed.scheme}://{urlparsed.netloc}"
        database = urlparsed.path[1:]

    return server_uri, database


class Mongo:
    def __init__(self) -> None:
        self._client: AsyncIOMotorClient | None = None
        self._engine: AIOEngine | None = None

    def init_app(self, app: Quart) -> None:
        server_uri, database = _parse(app.config["MONGO_URI"])

        self._client = AsyncIOMotorClient(server_uri)
        self._engine = AIOEngine(client=self._client, database=database)

    @property
    def odm(self) -> AIOEngine:
        return unwrap(self._engine)


async def init_mongo_database(mongo: Mongo) -> None:
    from .models import (
        BlueprintModel,
        BlueprintStatusModel,
        ConfigurationModel,
        InstallationModel,
        PolicyModel,
        PolicyStatusModel,
        PullRequestModel,
        ScorecardResultModel,
        StatisticsModel,
        TaskModel,
        UserModel,
    )

    await mongo.odm.configure_database(
        [
            InstallationModel,
            TaskModel,
            ConfigurationModel,
            PullRequestModel,
            StatisticsModel,
            UserModel,
            PolicyModel,
            PolicyStatusModel,
            BlueprintModel,
            BlueprintStatusModel,
            ScorecardResultModel,
        ]  # type: ignore
    )
