#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os
from io import StringIO
from logging import getLogger
from tempfile import TemporaryDirectory

from quart import render_template

from otterdog.config import OrganizationConfig, OtterdogConfig
from otterdog.operations.apply import ApplyOperation
from otterdog.utils import IndentingPrinter, LogLevel
from otterdog.webapp.tasks import get_rest_api_for_installation
from otterdog.webapp.webhook.github_models import PullRequest, Repository

from .validate_pull_request import escape_for_github, get_config

logger = getLogger(__name__)


async def apply_changes(
    org_id: str,
    installation_id: int,
    pull_request: PullRequest,
    repository: Repository,
    otterdog_config: OtterdogConfig,
) -> None:
    """Applies changes from a merged PR and adds the result as a comment."""

    if pull_request.base.ref != repository.default_branch:
        logger.info(
            "pull request merged into '%s' which is not the default branch '%s', ignoring",
            pull_request.base.ref,
            repository.default_branch,
        )
        return

    assert pull_request.merged is True
    assert pull_request.merge_commit_sha is not None

    logger.info("applying merged pull request #%d for repo '%s'", pull_request.number, repository.full_name)

    project_name = otterdog_config.get_project_name(org_id) or org_id
    pull_request_number = str(pull_request.number)

    rest_api = await get_rest_api_for_installation(installation_id)

    with TemporaryDirectory(dir=otterdog_config.jsonnet_base_dir) as work_dir:
        org_config = OrganizationConfig.of(
            project_name, org_id, {"provider": "inmemory", "api_token": rest_api.token}, work_dir, otterdog_config
        )

        jsonnet_config = org_config.jsonnet_config

        if not os.path.exists(jsonnet_config.org_dir):
            os.makedirs(jsonnet_config.org_dir)

        jsonnet_config.init_template()

        # get config from merge commit sha
        head_file = jsonnet_config.org_config_file
        await get_config(
            rest_api,
            org_id,
            org_id,
            otterdog_config.default_config_repo,
            head_file,
            pull_request.merge_commit_sha,
        )

        output = StringIO()
        printer = IndentingPrinter(output, log_level=LogLevel.ERROR)

        # let's create an apply operation that forces processing but does not update
        # any web UI settings and resources using credentials
        operation = ApplyOperation(
            force_processing=True,
            no_web_ui=True,
            update_webhooks=False,
            update_secrets=False,
            update_filter="",
            delete_resources=True,
            resolve_secrets=False,
        )
        operation.init(otterdog_config, printer)

        # TODO: we need to exclude any change that requires credentials or the web ui
        await operation.execute(org_config)

        text = output.getvalue()
        logger.info(text)

        result = await render_template("applied_changes.txt", result=escape_for_github(text))

        await rest_api.issue.create_comment(org_id, otterdog_config.default_config_repo, pull_request_number, result)
