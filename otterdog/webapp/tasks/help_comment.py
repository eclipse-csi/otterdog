#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from quart import render_template

from otterdog.webapp.tasks import get_rest_api_for_installation


async def create_help_comment(org_id: str, installation_id: int, repo_name: str, pull_request_number: int) -> None:
    rest_api = await get_rest_api_for_installation(installation_id)
    comment = await render_template("help_comment.txt")
    await rest_api.issue.create_comment(org_id, repo_name, str(pull_request_number), comment)
