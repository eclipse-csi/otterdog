#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import re
from logging import getLogger

from pydantic import ValidationError
from quart import Response, current_app

from otterdog.utils import LogLevel
from otterdog.webapp.db.service import (
    get_installation,
    update_installation_status,
    update_installations_from_config,
)
from otterdog.webapp.tasks.apply_changes import ApplyChangesTask
from otterdog.webapp.tasks.check_sync import CheckConfigurationInSyncTask
from otterdog.webapp.tasks.complete_pull_request import CompletePullRequestTask
from otterdog.webapp.tasks.fetch_config import FetchConfigTask
from otterdog.webapp.tasks.help_comment import HelpCommentTask
from otterdog.webapp.tasks.retrieve_team_membership import RetrieveTeamMembershipTask
from otterdog.webapp.tasks.update_pull_request import UpdatePullRequestTask
from otterdog.webapp.tasks.validate_pull_request import ValidatePullRequestTask
from otterdog.webapp.utils import refresh_otterdog_config

from .github_models import (
    InstallationEvent,
    IssueCommentEvent,
    PullRequestEvent,
    PushEvent,
)
from .github_webhook import GitHubWebhook

webhook = GitHubWebhook()

logger = getLogger(__name__)


@webhook.hook("pull_request")
async def on_pull_request_received(data):
    try:
        event = PullRequestEvent.model_validate(data)
    except ValidationError:
        logger.error("failed to load pull request event data", exc_info=True)
        return success()

    if event.installation is None or event.organization is None:
        return success()

    if not await targets_config_repo(event.repository.name, event.installation.id):
        return success()

    current_app.add_background_task(
        UpdatePullRequestTask(
            event.installation.id,
            event.organization.login,
            event.repository.name,
            event.pull_request,
        )
    )

    if event.action in ["opened", "ready_for_review"] and event.pull_request.draft is False:
        current_app.add_background_task(
            RetrieveTeamMembershipTask(
                event.installation.id,
                event.organization.login,
                event.repository.name,
                event.pull_request.number,
            )
        )

    if event.action in ["opened", "synchronize", "ready_for_review", "reopened"] and event.pull_request.draft is False:
        # schedule a validate task
        current_app.add_background_task(
            ValidatePullRequestTask(
                event.installation.id,
                event.organization.login,
                event.repository.name,
                event.pull_request,
            )
        )

        # schedule a check-sync task
        current_app.add_background_task(
            CheckConfigurationInSyncTask(
                event.installation.id,
                event.organization.login,
                event.repository.name,
                event.pull_request,
            )
        )

    elif event.action in ["closed"] and event.pull_request.merged is True:
        if event.pull_request.base.ref != event.repository.default_branch:
            return success()

        current_app.add_background_task(
            ApplyChangesTask(
                event.installation.id,
                event.organization.login,
                event.repository,
                event.pull_request,
            )
        )

    return success()


@webhook.hook("issue_comment")
async def on_issue_comment_received(data):
    try:
        event = IssueCommentEvent.model_validate(data)
    except ValidationError:
        logger.error("failed to load issue comment event data", exc_info=True)
        return success()

    if event.installation is None or event.organization is None:
        return success()

    # currently we only handle comments to pull requests
    if event.issue.pull_request is None:
        return success()

    if not await targets_config_repo(event.repository.name, event.installation.id):
        return success()

    if event.action in ["created", "edited"]:
        org_id = event.organization.login
        installation_id = event.installation.id

        if re.match(r"\s*/help\s*", event.comment.body) is not None:
            current_app.add_background_task(
                HelpCommentTask(
                    installation_id,
                    org_id,
                    event.repository.name,
                    event.issue.number,
                )
            )
            return success()
        elif re.match(r"\s*/team-info\s*", event.comment.body) is not None:
            current_app.add_background_task(
                RetrieveTeamMembershipTask(
                    installation_id,
                    org_id,
                    event.repository.name,
                    event.issue.number,
                )
            )
            return success()
        elif re.match(r"\s*/check-sync\s*", event.comment.body) is not None:
            current_app.add_background_task(
                CheckConfigurationInSyncTask(
                    installation_id,
                    org_id,
                    event.repository.name,
                    event.issue.number,
                )
            )
            return success()
        elif re.match(r"\s*/done\s*", event.comment.body) is not None:
            current_app.add_background_task(
                CompletePullRequestTask(
                    installation_id,
                    org_id,
                    event.repository.name,
                    event.issue.number,
                    event.sender.login,
                )
            )
            return success()

        m = re.match(r"\s*/validate(\s+info)?\s*", event.comment.body)
        if m is None:
            return success()

        log_level_str = m.group(1)
        log_level = LogLevel.WARN

        if log_level_str is not None and log_level_str.strip() == "info":
            log_level = LogLevel.INFO

        current_app.add_background_task(
            ValidatePullRequestTask(
                installation_id,
                org_id,
                event.repository.name,
                event.issue.number,
                log_level,
            )
        )

    return success()


@webhook.hook("push")
async def on_push_received(data):
    try:
        event = PushEvent.model_validate(data)
    except ValidationError:
        logger.error("failed to load push event data", exc_info=True)
        return success()

    # check if the push targets the default branch of the config repo of an installation,
    # in such a case, update the current config in the database
    if event.installation is not None and event.organization is not None:
        if event.ref != f"refs/heads/{event.repository.default_branch}":
            return success()

        if not await targets_config_repo(event.repository.name, event.installation.id):
            return success()

        current_app.add_background_task(
            FetchConfigTask(
                event.installation.id,
                event.organization.login,
                event.repository.name,
            )
        )
        return success()

    # if the otterdog config repo has been update, update all installations
    if (
        event.repository.name == current_app.config["OTTERDOG_CONFIG_REPO"]
        and event.repository.owner.login == current_app.config["OTTERDOG_CONFIG_OWNER"]
    ):
        if event.ref != f"refs/heads/{event.repository.default_branch}":
            return success()

        async def update_installations() -> None:
            config = await refresh_otterdog_config(event.after)
            await update_installations_from_config(config)

        current_app.add_background_task(update_installations)
        return success()

    return success()


@webhook.hook("installation")
async def on_installation_received(data):
    try:
        event = InstallationEvent.model_validate(data)
    except ValidationError:
        logger.error("failed to load installation event data", exc_info=True)
        return success()

    current_app.add_background_task(update_installation_status, event.installation.id, event.action)
    return success()


async def targets_config_repo(repo_name: str, installation_id: int) -> bool:
    installation = await get_installation(installation_id)
    if installation is None:
        logger.warning(f"received event for unknown installation '{installation_id}'")
        return False

    return repo_name == installation.config_repo


def success() -> Response:
    return Response({}, mimetype="application/json", status=200)
