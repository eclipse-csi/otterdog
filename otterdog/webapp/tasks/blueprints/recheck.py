#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from quart import render_template

from otterdog.webapp.blueprints import create_blueprint_from_model
from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.db.service import (
    get_blueprints_for_command,
    get_configuration_by_github_id,
    get_installation,
)
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.utils import get_base_url

if TYPE_CHECKING:
    from otterdog.webapp.blueprints import Blueprint
    from otterdog.webapp.db.models import ConfigurationModel


@dataclass
class RecheckResult:
    """What a `/otterdog recheck` command scheduled, rendered into the reply."""

    scheduled: dict[str, list[str]] = field(default_factory=dict)
    unknown_blueprint_id: str | None = None
    known_blueprint_ids: list[str] = field(default_factory=list)
    not_matching: list[str] = field(default_factory=list)
    permission_denied: bool = False


@dataclass(repr=False)
class RecheckBlueprintsTask(InstallationBasedTask, Task[RecheckResult]):
    """
    Forces an evaluation of blueprints, triggered by `/otterdog recheck [<blueprint-id>]`.

    In the configuration repository every repository matched by the blueprint's selector is
    evaluated, in any other repository only that repository. The `BLUEPRINT_CHECK_INTERVAL`
    and the per-repository status gate are bypassed.
    """

    installation_id: int
    org_id: str
    repo_name: str
    issue_number: int
    author: str
    blueprint_id: str | None = None

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
            pull_request=self.issue_number,
        )

    async def _execute(self) -> RecheckResult:
        self.logger.info(
            "rechecking blueprint(s) '%s' requested by '%s' in '%s/%s#%d'",
            self.blueprint_id or "*",
            self.author,
            self.org_id,
            self.repo_name,
            self.issue_number,
        )

        result = RecheckResult()

        if not await self.has_write_access(self.org_id, self.repo_name, self.author):
            result.permission_denied = True
            await self._reply(result)
            return result

        blueprint_models, result.known_blueprint_ids = await get_blueprints_for_command(self.org_id, self.blueprint_id)
        if self.blueprint_id is not None and len(blueprint_models) == 0:
            result.unknown_blueprint_id = self.blueprint_id
            await self._reply(result)
            return result

        installation = await get_installation(self.installation_id)
        config_model = await get_configuration_by_github_id(self.org_id)
        if installation is None or config_model is None:
            raise RuntimeError(f"no installation or configuration found for org '{self.org_id}'")

        is_config_repo = installation.config_repo == self.repo_name

        for model in blueprint_models:
            blueprint = create_blueprint_from_model(model)
            if is_config_repo:
                await self._recheck_matching_repositories(blueprint, config_model, result)
            else:
                await self._recheck_this_repository(blueprint, config_model, result)

        await self._reply(result)
        return result

    async def _recheck_matching_repositories(
        self, blueprint: Blueprint, config_model: ConfigurationModel, result: RecheckResult
    ) -> None:
        repos = await blueprint.matching_repositories(config_model)
        if len(repos) > 0:
            await blueprint.evaluate(self.installation_id, self.org_id, recheck=True)
            result.scheduled[blueprint.id] = repos

    async def _recheck_this_repository(
        self, blueprint: Blueprint, config_model: ConfigurationModel, result: RecheckResult
    ) -> None:
        if blueprint.matches_repo_name(config_model, self.repo_name):
            await blueprint.evaluate_repo(self.installation_id, self.org_id, self.repo_name, config_model)
            result.scheduled[blueprint.id] = [self.repo_name]
        else:
            result.not_matching.append(blueprint.id)

    async def _post_execute(self, result_or_exception: RecheckResult | Exception) -> None:
        if isinstance(result_or_exception, Exception):
            await self.comment_on_failure(
                self.org_id, self.repo_name, self.issue_number, self.author, "recheck", result_or_exception
            )

    async def _reply(self, result: RecheckResult) -> None:
        comment = await render_template(
            "comment/recheck_comment.txt",
            result=result,
            author=self.author,
            org_id=self.org_id,
            dashboard_url=f"{get_base_url()}/organizations/{self.org_id}",
        )

        rest_api = await self.rest_api
        await rest_api.issue.create_comment(self.org_id, self.repo_name, str(self.issue_number), comment)

    def __repr__(self) -> str:
        return (
            f"RecheckBlueprintsTask(repo='{self.org_id}/{self.repo_name}', "
            f"issue={self.issue_number}, blueprint='{self.blueprint_id}')"
        )
