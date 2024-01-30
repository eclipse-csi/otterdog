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
from otterdog.webapp.tasks import get_otterdog_config, refresh_otterdog_config
from otterdog.webapp.tasks.apply_changes import ApplyChangesTask
from otterdog.webapp.tasks.check_sync import CheckConfigurationInSyncTask
from otterdog.webapp.tasks.help_comment import HelpCommentTask
from otterdog.webapp.tasks.retrieve_team_membership import RetrieveTeamMembershipTask
from otterdog.webapp.tasks.validate_pull_request import ValidatePullRequestTask

from .github_models import IssueCommentEvent, PullRequestEvent, PushEvent
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

    otterdog_config = get_otterdog_config()

    if event.repository.name != otterdog_config.default_config_repo:
        return success()

    if event.action in ["opened", "ready_for_review"] and event.pull_request.draft is False:
        current_app.add_background_task(
            RetrieveTeamMembershipTask(
                event.installation.id,
                event.organization.login,
                event.repository,
                event.pull_request,
            ).execute
        )

    if event.action in ["opened", "synchronize", "ready_for_review", "reopened"] and event.pull_request.draft is False:
        current_app.add_background_task(
            ValidatePullRequestTask(
                event.installation.id,
                event.organization.login,
                event.repository,
                event.pull_request,
            ).execute
        )

    elif event.action in ["closed"] and event.pull_request.merged is True:
        current_app.add_background_task(
            ApplyChangesTask(
                event.installation.id,
                event.organization.login,
                event.repository,
                event.pull_request,
            ).execute
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

    otterdog_config = get_otterdog_config()

    if event.repository.name != otterdog_config.default_config_repo:
        return success()

    if event.action in ["created", "edited"] and "/pull/" in event.issue.html_url:
        org_id = event.organization.login
        installation_id = event.installation.id

        if re.match(r"\s*/help\s*", event.comment.body) is not None:
            current_app.add_background_task(
                HelpCommentTask(
                    installation_id,
                    org_id,
                    event.repository.name,
                    event.issue.number,
                ).execute
            )
            return success()
        elif re.match(r"\s*/team-info\s*", event.comment.body) is not None:
            current_app.add_background_task(
                RetrieveTeamMembershipTask(
                    installation_id,
                    org_id,
                    event.repository,
                    event.issue.number,
                ).execute
            )
            return success()
        elif re.match(r"\s*/check-sync\s*", event.comment.body) is not None:
            current_app.add_background_task(
                CheckConfigurationInSyncTask(
                    installation_id,
                    org_id,
                    event.repository,
                    event.issue.number,
                ).execute
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
                event.repository,
                event.issue.number,
                log_level,
            ).execute
        )

    return success()


@webhook.hook("push")
async def on_push_received(data):
    try:
        event = PushEvent.model_validate(data)
    except ValidationError:
        logger.error("failed to load push event data", exc_info=True)
        return success()

    if (
        event.repository.name != current_app.config["OTTERDOG_CONFIG_REPO"]
        or event.repository.owner.login != current_app.config["OTTERDOG_CONFIG_OWNER"]
    ):
        return success()

    if event.ref != f"refs/heads/{event.repository.default_branch}":
        return success()

    current_app.add_background_task(refresh_otterdog_config)
    return success()


def success() -> Response:
    return Response({}, mimetype="application/json", status=200)
