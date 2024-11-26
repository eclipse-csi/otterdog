#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass
from datetime import datetime

from aiohttp import ClientSession

from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.db.service import (
    update_or_create_scorecard_result,
)
from otterdog.webapp.tasks import (
    InstallationBasedTask,
    Task,
)


@dataclass(repr=False)
class SyncScorecardResultTask(InstallationBasedTask, Task[None]):
    installation_id: int
    org_id: str
    repo_name: str

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
        )

    async def _execute(self) -> None:
        self.logger.info(
            "syncing scorecard results for repo '%s/%s'",
            self.org_id,
            self.repo_name,
        )

        headers = {"accept": "application/json"}

        scorecard_url = f"https://api.securityscorecards.dev/projects/github.com/{self.org_id}/{self.repo_name}"
        async with ClientSession() as session, session.get(scorecard_url, headers=headers) as response:
            if response.ok:
                json_response = await response.json()
                date = datetime.fromisoformat(json_response["date"])
                score = json_response["score"]
                scorecard_version = json_response["scorecard"]["version"]
                checks = json_response["checks"]

                await update_or_create_scorecard_result(
                    self.org_id,
                    self.repo_name,
                    date,
                    score,
                    scorecard_version,
                    checks,
                )

    def __repr__(self) -> str:
        return f"SyncScorecardResultTask(repo={self.org_id}/{self.repo_name})"
