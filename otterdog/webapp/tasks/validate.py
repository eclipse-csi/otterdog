#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

import os
import re
import filecmp

from io import StringIO
from logging import getLogger

from otterdog.config import OtterdogConfig
from otterdog.operations.local_plan_operation import LocalPlanOperation
from otterdog.providers.github import RestApi
from otterdog.utils import IndentingPrinter, LogLevel

from otterdog.webapp.tasks import get_rest_api_for_installation
from otterdog.webapp.webhook.models import PullRequest, Repository

logger = getLogger(__name__)


def validate_pull_request(
    org_id: str,
    installation_id: int,
    pull_request: PullRequest,
    repository: Repository,
    otterdog_config: OtterdogConfig,
    log_level: LogLevel = LogLevel.WARN,
) -> None:
    """Validates a PR and adds the result as a comment."""

    logger.info(
        "validating pull request #%d for repo '%s' with level %s", pull_request.number, repository.full_name, log_level
    )

    pull_request_number = str(pull_request.number)

    rest_api = get_rest_api_for_installation(installation_id)

    org_config = otterdog_config.get_organization_config(org_id)
    org_config.credential_data = {"provider": "inmemory", "api_token": rest_api.token}
    jsonnet_config = org_config.jsonnet_config

    if not os.path.exists(jsonnet_config.org_dir):
        os.makedirs(jsonnet_config.org_dir)

    jsonnet_config.init_template()

    # get BASE config
    base_file = jsonnet_config.org_config_file + "-BASE"
    get_config(rest_api, org_id, org_id, otterdog_config.default_config_repo, base_file, pull_request.base.ref)

    # get HEAD config from PR
    head_file = jsonnet_config.org_config_file
    get_config(
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

    operation.execute(org_config)

    text = output.getvalue()
    logger.info(text)

    result = f"""
This is your friendly self-service bot. Please find below the validation of the requested configuration changes:

<details>
<summary>Diff for {pull_request.head.sha}</summary>

```diff
{escape_for_github(text)}
```

</details>

Add a comment `/help` to get a list of available commands.
    """

    rest_api.issue.create_comment(org_id, otterdog_config.default_config_repo, pull_request_number, result)


def get_config(rest_api: RestApi, org_id: str, owner: str, repo: str, filename: str, ref: str):
    path = f"otterdog/{org_id}.jsonnet"
    content = rest_api.content.get_content(
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
        ansi_escape = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]')
        line = ansi_escape.sub('', line)

        diff_escape = re.compile(r'(\s+)([-+!])(\s+)')
        line = diff_escape.sub(r'\g<2>\g<1>', line)

        diff_escape2 = re.compile(r'(\s+)(~)')
        line = diff_escape2.sub(r'!\g<1>', line)

        output.append(line)

    return "\n".join(output)
