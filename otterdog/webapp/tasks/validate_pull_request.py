#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import filecmp
import os
import re
from io import StringIO
from logging import getLogger
from tempfile import TemporaryDirectory
from typing import cast

from pydantic import ValidationError
from quart import render_template

from otterdog.config import OrganizationConfig, OtterdogConfig
from otterdog.operations.local_plan import LocalPlanOperation
from otterdog.providers.github import RestApi
from otterdog.utils import IndentingPrinter, LogLevel
from otterdog.webapp.tasks import get_rest_api_for_installation
from otterdog.webapp.webhook.github_models import PullRequest, Repository

logger = getLogger(__name__)


async def validate_pull_request(
    org_id: str,
    installation_id: int,
    pull_request_or_number: PullRequest | int,
    repository: Repository,
    otterdog_config: OtterdogConfig,
    log_level: LogLevel = LogLevel.WARN,
) -> None:
    """Validates a PR and adds the result as a comment."""

    rest_api = await get_rest_api_for_installation(installation_id)

    if isinstance(pull_request_or_number, int):
        response = await rest_api.pull_request.get_pull_request(org_id, repository.name, str(pull_request_or_number))
        try:
            pull_request = PullRequest.model_validate(response)
        except ValidationError:
            logger.error("failed to load pull request event data", exc_info=True)
            return
    else:
        pull_request = cast(PullRequest, pull_request_or_number)

    pull_request_number = str(pull_request.number)
    project_name = otterdog_config.get_project_name(org_id) or org_id

    logger.info(
        "validating pull request #%d for repo '%s' with level %s", pull_request.number, repository.full_name, log_level
    )

    with TemporaryDirectory(dir=otterdog_config.jsonnet_base_dir) as work_dir:
        org_config = OrganizationConfig.of(
            project_name, org_id, {"provider": "inmemory", "api_token": rest_api.token}, work_dir, otterdog_config
        )

        jsonnet_config = org_config.jsonnet_config
        if not os.path.exists(jsonnet_config.org_dir):
            os.makedirs(jsonnet_config.org_dir)

        jsonnet_config.init_template()

        # get BASE config
        base_file = jsonnet_config.org_config_file + "-BASE"
        await get_config(
            rest_api,
            org_id,
            org_id,
            otterdog_config.default_config_repo,
            base_file,
            pull_request.base.ref,
        )

        # get HEAD config from PR
        head_file = jsonnet_config.org_config_file
        await get_config(
            rest_api,
            org_id,
            pull_request.head.repo.owner.login,
            pull_request.head.repo.name,
            head_file,
            pull_request.head.ref,
        )

        if filecmp.cmp(base_file, head_file):
            logger.info("head and base config are identical, no need to validate")
            return

        output = StringIO()
        printer = IndentingPrinter(output, log_level=log_level)
        operation = LocalPlanOperation("-BASE", False, False, "")
        operation.init(otterdog_config, printer)

        await operation.execute(org_config)

        text = output.getvalue()
        logger.info(text)

        result = await render_template("validation.txt", sha=pull_request.head.sha, result=escape_for_github(text))

        await rest_api.issue.create_comment(org_id, otterdog_config.default_config_repo, pull_request_number, result)


async def get_config(rest_api: RestApi, org_id: str, owner: str, repo: str, filename: str, ref: str):
    path = f"otterdog/{org_id}.jsonnet"
    content = await rest_api.content.get_content(
        owner,
        repo,
        path,
        ref,
    )
    with open(filename, "w") as file:
        file.write(content)


def escape_for_github(text: str) -> str:
    lines = text.splitlines()

    output = []
    for line in lines:
        ansi_escape = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]")
        line = ansi_escape.sub("", line)

        diff_escape = re.compile(r"(\s+)([-+!])(\s+)")
        line = diff_escape.sub(r"\g<2>\g<1>", line)

        diff_escape2 = re.compile(r"(\s+)(~)")
        line = diff_escape2.sub(r"!\g<1>", line)

        output.append(line)

    return "\n".join(output)
