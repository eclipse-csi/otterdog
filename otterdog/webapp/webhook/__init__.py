#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from logging import getLogger
from tempfile import TemporaryDirectory

from pydantic import ValidationError
from quart import Response, current_app

from otterdog.config import OtterdogConfig
from otterdog.webapp.tasks.validate import validate_pull_request

from .github_webhook import GitHubWebhook
from .models import PullRequestEvent

webhook = GitHubWebhook()

logger = getLogger(__name__)


@webhook.hook("pull_request")
async def on_pull_request_received(data):
    try:
        event = PullRequestEvent.model_validate(data)
    except ValidationError:
        logger.error("failed to load pull request event data", exc_info=True)
        return

    # TODO: make the config configurable and load it, e.g. from github
    otterdog_config = OtterdogConfig("otterdog-test.json", False)

    if event.repository.name != otterdog_config.default_config_repo:
        return

    if event.action in ["opened", "synchronize", "edited", "reopened"] and event.pull_request.draft is False:
        with TemporaryDirectory() as tmp_dir_name:
            otterdog_config.jsonnet_base_dir = tmp_dir_name

            def validate():
                validate_pull_request(
                    event.organization.login,
                    event.installation.id,
                    event.pull_request,
                    event.repository,
                    otterdog_config,
                )

            current_app.add_background_task(validate)

    # elif event.action in ["closed"] and event.pull_request.merged is True:
    #     with TemporaryDirectory() as tmp_dir_name:
    #         otterdog_config.jsonnet_base_dir = tmp_dir_name
    #
    #         apply_pull_request(
    #             event.organization.login, event.installation.id, event.pull_request, event.repository, otterdog_config
    #         )

    return Response({}, mimetype="application/json", status=200)


@webhook.hook("issue_comment")
async def on_issue_comment_received(data):
    return Response({}, mimetype="application/json", status=200)
