#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

import re
from logging import getLogger
from tempfile import TemporaryDirectory
from typing import Any

from celery import shared_task  # type: ignore
from pydantic import ValidationError

from otterdog.config import OtterdogConfig
from . import get_rest_api_for_installation

from otterdog.webapp.webhook.models import IssueCommentEvent, PullRequest
from otterdog.webapp.tasks.validate import validate_pull_request
from ...utils import LogLevel

logger = getLogger(__name__)


@shared_task
def handle_issue_comment_event(event_data: dict[str, Any]) -> None:
    try:
        event = IssueCommentEvent.model_validate(event_data)
    except ValidationError:
        logger.error("failed to load issue comment event data", exc_info=True)
        return

    # TODO: make the config configurable and load it, e.g. from github
    otterdog_config = OtterdogConfig("otterdog-test.json", False)

    if event.repository.name != otterdog_config.default_config_repo:
        return

    if event.action in ["created", "edited"] and "/pull/" in event.issue.html_url:
        org_id = event.organization.login
        installation_id = event.installation.id

        if re.match(r"\s*/help\s*", event.comment.body) is not None:
            create_help_comment(org_id, installation_id, event.repository.name, event.issue.number)
            return

        m = re.match(r"\s*/validate(\s+info)?\s*", event.comment.body)
        if m is None:
            return

        log_level_str = m.group(1)

        log_level = LogLevel.WARN

        match log_level_str:
            case "info":
                log_level = LogLevel.INFO

        rest_api = get_rest_api_for_installation(installation_id)
        response = rest_api.pull_request.get_pull_request(org_id, event.repository.name, str(event.issue.number))

        try:
            pull_request = PullRequest.model_validate(response)
        except ValidationError:
            logger.error("failed to load pull request event data", exc_info=True)
            return

        with TemporaryDirectory() as tmp_dir_name:
            otterdog_config.jsonnet_base_dir = tmp_dir_name

            validate_pull_request(
                org_id, installation_id, pull_request, event.repository, otterdog_config, log_level=log_level
            )


def create_help_comment(org_id: str, installation_id: int, repo_name: str, pull_request_number: int) -> None:
    rest_api = get_rest_api_for_installation(installation_id)

    text = """
This is your friendly self-service bot. The following commands are supported:

- `/validate`: validates the configuration change if this PR touches the configuration
- `/validate info`: validates the configuration change, printing also validation infos
"""

    rest_api.issue.create_comment(org_id, repo_name, str(pull_request_number), text)
