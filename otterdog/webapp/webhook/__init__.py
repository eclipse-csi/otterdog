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
from otterdog.webapp.tasks import get_otterdog_config
from otterdog.webapp.tasks.apply_changes import apply_changes
from otterdog.webapp.tasks.help_comment import create_help_comment
from otterdog.webapp.tasks.validate_pull_request import validate_pull_request

from .github_models import IssueCommentEvent, PullRequestEvent
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

    otterdog_config = get_otterdog_config()

    if event.repository.name != otterdog_config.default_config_repo:
        return success()

    if event.action in ["opened", "synchronize", "ready_for_review", "reopened"] and event.pull_request.draft is False:

        async def validate():
            await validate_pull_request(
                event.organization.login,
                event.installation.id,
                event.pull_request,
                event.repository,
                otterdog_config,
            )

        current_app.add_background_task(validate)

    elif event.action in ["closed"] and event.pull_request.merged is True:

        async def apply():
            await apply_changes(
                event.organization.login,
                event.installation.id,
                event.pull_request,
                event.repository,
                otterdog_config,
            )

        current_app.add_background_task(apply)

    return success()


@webhook.hook("issue_comment")
async def on_issue_comment_received(data):
    try:
        event = IssueCommentEvent.model_validate(data)
    except ValidationError:
        logger.error("failed to load issue comment event data", exc_info=True)
        return success()

    otterdog_config = get_otterdog_config()

    if event.repository.name != otterdog_config.default_config_repo:
        return success()

    if event.action in ["created", "edited"] and "/pull/" in event.issue.html_url:
        org_id = event.organization.login
        installation_id = event.installation.id

        if re.match(r"\s*/help\s*", event.comment.body) is not None:

            async def help_comment():
                await create_help_comment(org_id, installation_id, event.repository.name, event.issue.number)

            current_app.add_background_task(help_comment)
            return success()

        m = re.match(r"\s*/validate(\s+info)?\s*", event.comment.body)
        if m is None:
            return success()

        log_level_str = m.group(1)
        log_level = LogLevel.WARN

        if log_level_str is not None and log_level_str.strip() == "info":
            log_level = LogLevel.INFO

        async def validate():
            await validate_pull_request(
                org_id,
                installation_id,
                event.issue.number,
                event.repository,
                otterdog_config,
                log_level=log_level,
            )

        current_app.add_background_task(validate)

    return success()


def success() -> Response:
    return Response({}, mimetype="application/json", status=200)
