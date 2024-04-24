#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from ariadne import graphql
from ariadne.explorer import ExplorerGraphiQL
from quart import jsonify, request

from otterdog.webapp.db.service import (
    get_configuration_by_github_id,
    get_configuration_by_project_name,
    get_installations,
    get_merged_pull_requests_paged,
    get_tasks_paged,
)

from . import blueprint

explorer_html = ExplorerGraphiQL(title="Otterdog GraphQL").html(None)


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


@blueprint.route("/tasks")
async def tasks():
    paged_tasks, count = await get_tasks_paged(request.args.to_dict())
    result = {"data": list(map(lambda x: x.model_dump(exclude={"id"}), paged_tasks)), "itemsCount": count}
    return jsonify(result)


@blueprint.route("/pullrequests/merged")
async def merged_pullrequests():
    paged_pull_requests, count = await get_merged_pull_requests_paged(request.args.to_dict())
    result = {"data": list(map(lambda x: x.model_dump(), paged_pull_requests)), "itemsCount": count}
    return jsonify(result)


@blueprint.route("/graphql", methods=["GET"])
async def graphql_playground():
    return explorer_html, 200


@blueprint.route("/graphql", methods=["POST"])
async def graphql_server():
    from .graphql import schema

    data = await request.get_json()

    success, result = await graphql(schema, data, context_value=request, debug=False)

    status_code = 200 if success else 400
    return jsonify(result), status_code
