#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

import os

from io import StringIO
from logging import getLogger

from otterdog.config import OtterdogConfig
from otterdog.operations.apply_operation import ApplyOperation
from otterdog.utils import IndentingPrinter, LogLevel

from otterdog.webapp.tasks import get_rest_api_for_installation
from otterdog.webapp.webhook.models import PullRequest, Repository

from .validate import get_config, escape_for_github

logger = getLogger(__name__)


def apply_pull_request(
    org_id: str,
    installation_id: int,
    pull_request: PullRequest,
    repository: Repository,
    otterdog_config: OtterdogConfig,
) -> None:
    """Validates a PR and adds the result as a comment."""

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

    pull_request_number = str(pull_request.number)

    rest_api = get_rest_api_for_installation(installation_id)

    org_config = otterdog_config.get_organization_config(org_id)
    org_config.credential_data = {"provider": "plain", "api_token": rest_api.token}
    jsonnet_config = org_config.jsonnet_config

    if not os.path.exists(jsonnet_config.org_dir):
        os.makedirs(jsonnet_config.org_dir)

    jsonnet_config.init_template()

    # get config from merge commit sha
    head_file = jsonnet_config.org_config_file
    get_config(
        rest_api,
        org_id,
        org_id,
        otterdog_config.default_config_repo,
        head_file,
        pull_request.merge_commit_sha,
    )

    output = StringIO()
    printer = IndentingPrinter(output, log_level=LogLevel.ERROR)
    operation = ApplyOperation(True, True, False, False, "", False)
    operation.init(otterdog_config, printer)

    operation.execute(org_config)

    text = output.getvalue()
    logger.info(text)

    result = f"""
Changes have been applied:

```diff
{escape_for_github(text)}
```
"""

    rest_api.issue.create_comment(org_id, otterdog_config.default_config_repo, pull_request_number, result)
