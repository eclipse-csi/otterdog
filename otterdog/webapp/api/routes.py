#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from quart import jsonify

from otterdog.webapp.db.service import (
    get_configuration_by_github_id,
    get_configuration_by_project_name,
    get_installations,
)

from . import blueprint


@blueprint.route("/organizations")
async def organizations():
    installations = await get_installations()
    result = list(map(lambda x: x.model_dump(include={"github_id", "project_name"}), installations))
    return jsonify(result)


@blueprint.route("/organizations/<github_id>")
async def organization(github_id: str):
    config = await get_configuration_by_github_id(github_id)
    if config is None:
        return {}, 404
    else:
        return jsonify(config.config)


@blueprint.route("/projects/<project_name>")
async def project(project_name: str):
    config = await get_configuration_by_project_name(project_name)
    if config is None:
        return {}, 404
    else:
        return jsonify(config.config)
