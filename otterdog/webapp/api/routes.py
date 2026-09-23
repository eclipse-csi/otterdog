#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from datetime import datetime, timedelta
from logging import getLogger

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
from otterdog.webapp.statistics import get_pull_request_activity_job
from otterdog.webapp.utils import current_utc_time

from . import blueprint

logger = getLogger(__name__)

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


# supported time ranges of the pull request statistics, mapped to their length in days,
# "all" covers the complete history and thus has no lower bound
_STATISTICS_RANGES = {"7d": 7, "14d": 14, "30d": 30, "90d": 90, "6m": 183, "12m": 365, "all": None}


def _statistics_parameters() -> tuple[str, str, str | None]:
    return (
        request.args.get("interval", "month"),
        request.args.get("range", "12m"),
        request.args.get("org") or None,
    )


def _validate_statistics_parameters(interval: str, time_range: str) -> str | None:
    if interval not in ("day", "week", "month"):
        return f"unsupported interval '{interval}'"

    if time_range not in _STATISTICS_RANGES:
        return f"unsupported range '{time_range}'"

    return None


def _since_of_range(time_range: str) -> datetime | None:
    """
    Start of the given range, inclusive of today.

    The aggregation buckets by whole days, so a range of 7 days has to start 6 days before
    today, otherwise today plus the seven preceding days make eight daily buckets.
    """

    days = _STATISTICS_RANGES[time_range]
    if days is None:
        return None

    today = current_utc_time().replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(days=days - 1)


@blueprint.route("/pullrequests/statistics/progress")
async def pullrequest_statistics_progress():
    """
    Reports the progress of collecting the pull request statistics, starting the collection on
    the first call and returning the result once it is done.

    Polling with short requests is used rather than a single long running one, as collecting
    the data of all organizations easily outlives the request timeout of a reverse proxy.
    """

    interval, time_range, org_id = _statistics_parameters()

    error = _validate_statistics_parameters(interval, time_range)
    if error is not None:
        return {"error": error}, 400

    since = _since_of_range(time_range)
    return jsonify(await get_pull_request_activity_job(interval, time_range, since, org_id))


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
