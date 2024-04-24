#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass

from quart import render_template

from otterdog.webapp.db.models import PullRequestStatus, TaskModel
from otterdog.webapp.db.service import find_pull_request
from otterdog.webapp.tasks import (
    InstallationBasedTask,
    Task,
    contains_eligible_team_for_auto_merge,
)
from otterdog.webapp.webhook.github_models import PullRequest


@dataclass(repr=False)
class MergePullRequestTask(InstallationBasedTask, Task[None]):
    installation_id: int
    org_id: str
    repo_name: str
    pull_request_number: int
    author: str

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
            pull_request=self.pull_request_number,
        )

    async def _pre_execute(self) -> bool:
        self.logger.info(
            "auto-merging pull request #%d on behalf of user '%s' for repo '%s/%s'",
            self.pull_request_number,
            self.author,
            self.org_id,
            self.repo_name,
        )

        pr_model = await find_pull_request(self.org_id, self.repo_name, self.pull_request_number)
        if pr_model is None:
            raise RuntimeError(
                f"failed to fetch pull request #{self.pull_request_number} in repo '{self.org_id}/{self.repo_name}'"
            )
        else:
            self._pr_model = pr_model

        if pr_model.status != PullRequestStatus.OPEN:
            self.logger.info(
                f"pull request #{self.pull_request_number} for repo '{self.org_id}/{self.repo_name}' "
                "is not open, skipping"
            )
            return False

        if pr_model.can_be_automerged() is False:
            self.logger.info(
                f"pull request #{self.pull_request_number} for repo '{self.org_id}/{self.repo_name}' "
                "is not eligible for auto-merge, skipping"
            )
            return False

        rest_api = await self.rest_api
        response = await rest_api.pull_request.get_pull_request(
            self.org_id, self.repo_name, str(self.pull_request_number)
        )
        pull_request = PullRequest.model_validate(response)

        if self.author != pull_request.user.login:
            # if somebody else as the creator of the pull requests added the comment,
            # check if the author is eligible for auto merge.

            graphql_api = await self.graphql_api
            team_data = await graphql_api.get_team_membership(self.org_id, self.author)
            team_membership = [team["name"] for team in team_data]

            if not contains_eligible_team_for_auto_merge(team_membership):
                comment = await render_template("comment/wrong_user_merge_comment.txt")
                await rest_api.issue.create_comment(self.org_id, self.repo_name, str(self.pull_request_number), comment)

                self.logger.error(
                    f"merge for pull request #{self.pull_request_number} triggered by user '{self.author}' "
                    "who is not the creator of the PR and not eligible for auto-merge, skipping"
                )

                return False

        return True

    async def _execute(self) -> None:
        rest_api = await self.rest_api
        merged = await rest_api.pull_request.merge(self.org_id, self.repo_name, str(self.pull_request_number))

        if merged is True:
            self.logger.info(f"Pull Request #{self.pull_request_number} auto-merged")
        else:
            self.logger.error(f"Pull Request #{self.pull_request_number} failed to auto-merge")

    def __repr__(self) -> str:
        return f"MergePullRequestTask(repo='{self.org_id}/{self.repo_name}', pull_request=#{self.pull_request_number})"
