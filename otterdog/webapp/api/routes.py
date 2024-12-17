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
    get_blueprints_with_remediations_paged,
    get_configuration_by_github_id,
    get_configuration_by_project_name,
    get_dismissed_blueprints_paged,
    get_installations,
    get_merged_pull_requests_paged,
    get_open_pull_requests_paged,
    get_scorecard_results_paged,
    get_tasks_paged,
)

from . import blueprint

explorer_html = ExplorerGraphiQL(title="Otterdog GraphQL").html(None)


@blueprint.route("/organizations")
async def organizations():
    installations = await get_installations()
    result = [x.model_dump(include={"github_id", "project_name"}) for x in installations]
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
    result = {"data": [x.model_dump(exclude={"id"}) for x in paged_tasks], "itemsCount": count}
    return jsonify(result)


@blueprint.route("/pullrequests/open")
async def open_pullrequests():
    paged_pull_requests, count = await get_open_pull_requests_paged(request.args.to_dict())
    result = {"data": [x.model_dump() for x in paged_pull_requests], "itemsCount": count}
    return jsonify(result)


@blueprint.route("/pullrequests/merged")
async def merged_pullrequests():
    paged_pull_requests, count = await get_merged_pull_requests_paged(request.args.to_dict())
    result = {"data": [x.model_dump() for x in paged_pull_requests], "itemsCount": count}
    return jsonify(result)


@blueprint.route("/blueprints/remediations")
async def blueprints_with_remediations():
    paged_blueprints, count = await get_blueprints_with_remediations_paged(request.args.to_dict())
    result = {"data": [x.model_dump() for x in paged_blueprints], "itemsCount": count}
    return jsonify(result)


@blueprint.route("/blueprints/dismissed")
async def dismissed_blueprints():
    paged_blueprints, count = await get_dismissed_blueprints_paged(request.args.to_dict())
    result = {"data": [x.model_dump() for x in paged_blueprints], "itemsCount": count}
    return jsonify(result)


@blueprint.route("/scorecard/results")
async def scorecard_results():
    paged_scorecard_results, count = await get_scorecard_results_paged(request.args.to_dict())

    def json_transform(m):
        json = m.model_dump()
        for check in json["checks"]:
            json.update({check["name"]: check["score"]})
        return json

    result = {"data": [json_transform(x) for x in paged_scorecard_results], "itemsCount": count}
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
