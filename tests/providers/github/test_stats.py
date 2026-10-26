#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio
import json
from types import SimpleNamespace

import pretend
import pytest
from importlib_resources import files
from rich.console import Console
from yarl import URL

from otterdog import resources
from otterdog.providers.github.stats import (
    ApiUsage,
    RateLimit,
    RequestOutcome,
    RequestRecorder,
    RequestStatistics,
    collect_api_usage,
    rest_endpoint,
)
from otterdog.providers.github.stats.report import ApiUsageReport


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("get", "/orgs/acme", "GET /orgs/{org}"),
        ("GET", "/orgs/acme/repos", "GET /orgs/{org}/repos"),
        ("GET", "/repos/acme/website", "GET /repos/{owner}/{repo}"),
        ("GET", "/repos/acme/website/environments/production", "GET /repos/{owner}/{repo}/environments/{name}"),
        (
            "PUT",
            "/repos/acme/website/environments/production/secrets/TOKEN",
            "PUT /repos/{owner}/{repo}/environments/{name}/secrets/{name}",
        ),
        (
            "GET",
            "/repos/acme/website/environments/production/secrets/public-key",
            "GET /repos/{owner}/{repo}/environments/{name}/secrets/public-key",
        ),
        ("GET", "/orgs/acme/actions/secrets/public-key", "GET /orgs/{org}/actions/secrets/public-key"),
        (
            "GET",
            "/orgs/acme/actions/secrets/TOKEN/repositories",
            "GET /orgs/{org}/actions/secrets/{name}/repositories",
        ),
        ("GET", "/orgs/acme/actions/permissions/workflow", "GET /orgs/{org}/actions/permissions/workflow"),
        ("PATCH", "/orgs/acme/hooks/1234", "PATCH /orgs/{org}/hooks/{id}"),
        ("GET", "/orgs/acme/rulesets/42", "GET /orgs/{org}/rulesets/{id}"),
        ("GET", "/orgs/acme/teams/developers/members", "GET /orgs/{org}/teams/{name}/members"),
        (
            "PUT",
            "/orgs/acme/teams/developers/repos/acme/website",
            "PUT /orgs/{org}/teams/{name}/repos/{owner}/{repo}",
        ),
        (
            "PUT",
            "/orgs/acme/organization-roles/teams/developers/8",
            "PUT /orgs/{org}/organization-roles/teams/{name}/{id}",
        ),
        ("GET", "/orgs/acme/organization-roles/8/teams", "GET /orgs/{org}/organization-roles/{id}/teams"),
        (
            "GET",
            "/orgs/acme/code-security/configurations/defaults",
            "GET /orgs/{org}/code-security/configurations/defaults",
        ),
        ("PUT", "/orgs/acme/properties/schema/team", "PUT /orgs/{org}/properties/schema/{name}"),
        ("GET", "/repos/acme/website/properties/values", "GET /repos/{owner}/{repo}/properties/values"),
        (
            "POST",
            "/repos/acme/website/branches/main/rename",
            "POST /repos/{owner}/{repo}/branches/{name}/rename",
        ),
        # names of branches and refs may contain slashes
        ("GET", "/repos/acme/website/branches/feature/private-project", "GET /repos/{owner}/{repo}/branches/{name}"),
        (
            "POST",
            "/repos/acme/website/branches/feature/private-project/rename",
            "POST /repos/{owner}/{repo}/branches/{name}/rename",
        ),
        # route words within names do not split them
        (
            "POST",
            "/repos/acme/website/branches/feature/rename/private-project/rename",
            "POST /repos/{owner}/{repo}/branches/{name}/rename",
        ),
        (
            "GET",
            "/repos/acme/website/branches/feature/rename/private-project",
            "GET /repos/{owner}/{repo}/branches/{name}",
        ),
        # a route is only matched with its method
        ("GET", "/repos/acme/website/branches/feature/rename", "GET /repos/{owner}/{repo}/branches/{name}"),
        ("GET", "/repos/acme/website/branches/rename", "GET /repos/{owner}/{repo}/branches/{name}"),
        # routes not used by otterdog are replaced together with the name
        (
            "GET",
            "/repos/acme/website/branches/release/1.x/protection/required_status_checks",
            "GET /repos/{owner}/{repo}/branches/{name}",
        ),
        ("GET", "/repos/acme/website/commits/release/1.x", "GET /repos/{owner}/{repo}/commits/{name}"),
        (
            "GET",
            "/repos/acme/website/commits/release/1.x/statuses",
            "GET /repos/{owner}/{repo}/commits/{name}/statuses",
        ),
        (
            "GET",
            "/repos/acme/website/commits/fix/statuses/private/statuses",
            "GET /repos/{owner}/{repo}/commits/{name}/statuses",
        ),
        ("GET", "/repos/acme/website/commits/fix/status", "GET /repos/{owner}/{repo}/commits/{name}"),
        ("GET", "/repos/acme/website/commits/abc123/pulls", "GET /repos/{owner}/{repo}/commits/{name}/pulls"),
        # names of environments may contain slashes, sent as is or encoded
        (
            "PUT",
            "/repos/acme/website/environments/preview/private-project",
            "PUT /repos/{owner}/{repo}/environments/{name}",
        ),
        ("GET", "/repos/acme/website/environments/preview%2Fprivate", "GET /repos/{owner}/{repo}/environments/{name}"),
        (
            "PUT",
            "/repos/acme/website/environments/preview/private/secrets/TOKEN",
            "PUT /repos/{owner}/{repo}/environments/{name}/secrets/{name}",
        ),
        (
            "GET",
            "/repos/acme/website/environments/preview/private/secrets/public-key",
            "GET /repos/{owner}/{repo}/environments/{name}/secrets/public-key",
        ),
        (
            "GET",
            "/repos/acme/website/environments/preview/private/variables",
            "GET /repos/{owner}/{repo}/environments/{name}/variables",
        ),
        (
            "DELETE",
            "/repos/acme/website/environments/preview/private/deployment-branch-policies/12",
            "DELETE /repos/{owner}/{repo}/environments/{name}/deployment-branch-policies/{id}",
        ),
        # literal segments only follow their own collection
        (
            "PUT",
            "/repos/acme/website/environments/teams/secrets/PRIVATE_TOKEN",
            "PUT /repos/{owner}/{repo}/environments/{name}/secrets/{name}",
        ),
        ("GET", "/orgs/acme/teams/teams/members", "GET /orgs/{org}/teams/{name}/members"),
        ("GET", "/orgs/acme/teams/public-key/members", "GET /orgs/{org}/teams/{name}/members"),
        ("PUT", "/orgs/acme/teams/developers/memberships/teams", "PUT /orgs/{org}/teams/{name}/memberships/{name}"),
        ("GET", "/orgs/acme/actions/secrets/defaults", "GET /orgs/{org}/actions/secrets/{name}"),
        ("GET", "/repos/acme/website/contents/docs/index.md", "GET /repos/{owner}/{repo}/contents/{path}"),
        ("GET", "/repos/acme/website/zipball/main", "GET /repos/{owner}/{repo}/zipball/{ref}"),
        ("GET", "/repos/acme/website/git/refs/heads/feature/x", "GET /repos/{owner}/{repo}/git/refs/{ref}"),
        ("POST", "/repos/acme/website/git/refs", "POST /repos/{owner}/{repo}/git/refs"),
        ("GET", "/repos/acme/website/commits/abc123/statuses", "GET /repos/{owner}/{repo}/commits/{name}/statuses"),
        (
            "POST",
            "/repos/acme/website/actions/workflows/ci.yml/dispatches",
            "POST /repos/{owner}/{repo}/actions/workflows/{name}/dispatches",
        ),
        (
            "GET",
            "/repos/acme/website/actions/artifacts/77/zip",
            "GET /repos/{owner}/{repo}/actions/artifacts/{id}/zip",
        ),
        ("GET", "/repos/acme/website/pulls/12/reviews", "GET /repos/{owner}/{repo}/pulls/{id}/reviews"),
        ("POST", "/app/installations/99/access_tokens", "POST /app/installations/{id}/access_tokens"),
        ("GET", "/apps/otterdog", "GET /apps/{name}"),
        ("GET", "/users/octocat", "GET /users/{user}"),
        ("GET", "/user/1234", "GET /user/{id}"),
        ("GET", "/repositories/1234", "GET /repositories/{id}"),
        ("GET", "/rate_limit", "GET /rate_limit"),
        ("POST", "/graphql", "POST /graphql"),
        ("GET", "/orgs/acme/", "GET /orgs/{org}"),
    ],
)
def test_rest_endpoint(method, path, expected):
    assert rest_endpoint(method, path) == expected


def test_record_classifies_requests_into_subsets():
    statistics = RequestStatistics()

    statistics.record(RequestOutcome("GET /orgs/{org}", quota_resource="core"))
    statistics.record(RequestOutcome("GET /orgs/{org}", retry=True, error="502", quota_resource="core"))
    statistics.record(RequestOutcome("GET /orgs/{org}/hooks", cached=True))
    statistics.record(RequestOutcome("GET /orgs/{org}/hooks", error="network"))
    statistics.record(RequestOutcome("GET /orgs/{org}/hooks", interrupted=True))

    assert statistics.total_requests == 5
    assert statistics.retried_requests == 1
    assert statistics.errors == {"502": 1, "network": 1}
    assert statistics.error_count == 2
    assert statistics.cached_responses == 1
    assert statistics.interrupted_requests == 1
    assert statistics.quota_cost == {"core": 2}
    assert statistics.endpoints["GET /orgs/{org}"].requests == 2
    assert statistics.endpoints["GET /orgs/{org}"].quota_cost == 2
    assert statistics.endpoints["GET /orgs/{org}/hooks"].requests == 3
    assert statistics.endpoints["GET /orgs/{org}/hooks"].quota_cost == 0


def test_rate_limit_keeps_lowest_remaining_of_current_window():
    statistics = RequestStatistics()
    assert statistics.remaining_rate_limit == -1

    statistics.update_rate_limit(RateLimit("core", 5000, 4000, 1000), now=500)

    # concurrent responses arrive in any order
    statistics.update_rate_limit(RateLimit("core", 5000, 4100, 1000), now=510)
    assert statistics.rate_limits["core"].remaining == 4000

    statistics.update_rate_limit(RateLimit("core", 5000, 3900, 1000), now=520)
    assert statistics.rate_limits["core"].remaining == 3900

    # a later reset time while the current window has not ended is not a new window
    statistics.update_rate_limit(RateLimit("core", 5000, 5000, 4130), now=530)
    assert statistics.rate_limits["core"] == RateLimit("core", 5000, 3900, 1000)

    # once the current window has ended, the quota has been reset
    statistics.update_rate_limit(RateLimit("core", 5000, 4999, 4600), now=1000)
    assert statistics.rate_limits["core"].remaining == 4999

    # a delayed response of the window that has ended is ignored
    statistics.update_rate_limit(RateLimit("core", 5000, 3900, 1000), now=1001)
    assert statistics.rate_limits["core"] == RateLimit("core", 5000, 4999, 4600)

    statistics.update_rate_limit(RateLimit("search", 30, 25, 4600), now=1000)
    assert statistics.remaining_rate_limit == 25


def test_rate_limit_is_not_reset_by_responses_reflecting_no_consumption():
    # responses that do not reflect any consumption report the full quota with a reset time one hour from now
    statistics = RequestStatistics()

    for second in range(0, 180, 10):
        statistics.update_rate_limit(RateLimit("core", 5000, 4990 - second // 10, 3600), now=second)
        statistics.update_rate_limit(RateLimit("core", 5000, 5000, 3600 + second), now=second)

    assert statistics.rate_limits["core"] == RateLimit("core", 5000, 4973, 3600)


def test_merge():
    first = RequestStatistics()
    first.record(RequestOutcome("GET /orgs/{org}", quota_resource="core", rate_limit=RateLimit("core", 5000, 10, 1)))
    first.record_unpriced_request()

    second = RequestStatistics()
    second.record(RequestOutcome("GET /orgs/{org}", retry=True, error="404", quota_resource="core"))
    second.record(RequestOutcome("GET /orgs/{org}/repos", cached=True, rate_limit=RateLimit("core", 5000, 5, 1)))

    first.merge(second)

    assert first.total_requests == 3
    assert first.retried_requests == 1
    assert first.cached_responses == 1
    assert first.unpriced_requests == 1
    assert first.errors == {"404": 1}
    assert first.quota_cost == {"core": 2}
    assert first.endpoints["GET /orgs/{org}"].requests == 2
    assert first.remaining_rate_limit == 5


async def test_collect_api_usage_isolates_concurrent_tasks():
    recorder = RequestRecorder("rest", RequestStatistics())
    run_usage = ApiUsage()

    async def run(usage: ApiUsage, count: int) -> None:
        with collect_api_usage(usage):
            for _ in range(count):
                recorder.record(RequestOutcome("GET /meta"))
                await asyncio.sleep(0)

    first = ApiUsage()
    second = ApiUsage()

    with collect_api_usage(run_usage):
        await asyncio.gather(run(first, 10), run(second, 20))

    # outside of any collection, only the client statistics are updated
    recorder.record(RequestOutcome("GET /meta"))

    assert first.rest.total_requests == 10
    assert second.rest.total_requests == 20
    assert run_usage.rest.total_requests == 30
    assert run_usage.graphql.total_requests == 0


def test_api_usage_of_unknown_api():
    usage = ApiUsage()

    with pytest.raises(ValueError, match="unknown api"):
        usage.of("soap")


def _sample_report() -> ApiUsageReport:
    report = ApiUsageReport("plan")

    for github_id, count in [("acme", 3), ("globex", 1)]:
        with collect_api_usage(report.total), collect_api_usage(report.organization(github_id)):
            rest = RequestRecorder("rest", RequestStatistics())
            for _ in range(count):
                rest.record(
                    RequestOutcome(
                        "GET /orgs/{org}",
                        quota_resource="core",
                        rate_limit=RateLimit("core", 5000, 4321, 1_800_000_000),
                    )
                )
            rest.record(RequestOutcome("GET /orgs/{org}/hooks", cached=True))
            rest.record(RequestOutcome("GET /orgs/{org}/hooks", retry=True, error="404", quota_resource="core"))

            graphql = RequestRecorder("graphql", RequestStatistics())
            graphql.record(RequestOutcome("query get-team-membership"))
            graphql.add_quota_cost("graphql", 2, "query get-team-membership")
            graphql.record(RequestOutcome("mutation minimizeComment"))
            graphql.record_unpriced_request()

    report.finish("completed")
    return report


def test_report_to_json():
    data = _sample_report().to_json()

    assert data["command"] == "plan"
    assert data["outcome"] == "completed"
    assert data["total"]["requests"] == 12
    assert data["total"]["retries"] == 2
    assert data["total"]["errors"] == {"404": 2}
    assert data["total"]["cached"] == 2
    assert data["total"]["quota_cost"] == {"core": 6, "graphql": 4}
    assert data["apis"]["rest"]["requests"] == 8
    assert data["apis"]["rest"]["endpoints"]["GET /orgs/{org}"] == {"requests": 4, "quota_cost": 4}
    assert data["apis"]["graphql"]["unpriced_requests"] == 2
    assert data["rate_limits"]["core"]["remaining"] == 4321
    assert data["rate_limits"]["core"]["reset"].startswith("2027-01-15T")
    assert data["organizations"]["acme"]["rest"]["requests"] == 5
    assert data["organizations"]["globex"]["rest"]["requests"] == 3
    assert "endpoints" not in data["organizations"]["acme"]["rest"]
    # the report is serializable as is
    json.dumps(data)


def test_report_print():
    console = Console(record=True, width=120)

    _sample_report().print(console, detailed=True)
    output = console.export_text()

    assert "GitHub API usage · plan · 2 organizations" in output
    assert "~6 core" in output
    assert "4 points + 2 unpriced" in output
    assert "Errors:      404: 2" in output
    assert "Rate limit:  core  4,321/5,000 left  resets 08:00 UTC" in output
    # the details are separated from the table by an empty line
    lines = output.splitlines()
    total_index = next(i for i, line in enumerate(lines) if line.strip().startswith("Total"))
    assert lines[total_index + 1].strip() == ""
    assert lines[total_index + 2].startswith("  Errors:")
    assert "Per organization" in output
    rows = [" ".join(line.split()) for line in output.splitlines()]
    assert "acme 7 1 1 1 ~4 core · 2 points + 1 unpriced" in rows
    assert "globex 5 1 1 1 ~2 core · 2 points + 1 unpriced" in rows
    assert "Top endpoints" in output
    assert "query get-team-membership" in output
    assert "Web UI" not in output


def test_report_prints_top_organizations_unless_detailed():
    report = ApiUsageReport("validate")
    for index in range(12):
        recorder = RequestRecorder("rest", RequestStatistics())
        with collect_api_usage(report.organization(f"org-{index:02d}")):
            for _ in range(index):
                recorder.record(RequestOutcome("GET /orgs/{org}/members"))
    report.finish("completed")

    console = Console(record=True, width=120)
    report.print(console)
    output = console.export_text()

    assert "Top 10 of 12 organizations" in output
    assert "org-11" in output
    assert "org-02" in output
    assert "org-01" not in output
    assert "use -v to list all organizations" in output

    console = Console(record=True, width=120)
    report.print(console, detailed=True)
    output = console.export_text()

    assert "Per organization" in output
    assert "org-00" in output
    assert "use -v" not in output


def test_report_prints_one_aligned_line_per_rate_limit():
    report = ApiUsageReport("plan")
    report.total.rest.update_rate_limit(RateLimit("core", 5000, 4923, 1_800_000_000))
    report.total.rest.update_rate_limit(RateLimit("webhook_deliveries", 500, 496, 1_800_000_000))
    report.total.graphql.update_rate_limit(RateLimit("graphql", 5000, 4956, 1_800_000_120))
    report.finish("completed")

    console = Console(record=True, width=120)
    report.print(console)
    lines = [x.rstrip() for x in console.export_text().splitlines() if "left" in x]

    assert lines == [
        "  Rate limit:  core                4,923/5,000 left  resets 08:00 UTC",
        "               graphql             4,956/5,000 left  resets 08:02 UTC",
        "               webhook_deliveries      496/500 left  resets 08:00 UTC",
    ]


def test_report_print_failed_without_requests():
    console = Console(record=True, width=120)

    report = ApiUsageReport("validate")
    report.finish("failed")
    report.print(console)
    output = console.export_text()

    assert "validate · 0 organizations" in output
    assert "failed" in output
    assert "Rate limit" not in output
    assert "Not sent" not in output


def test_report_lists_unsent_attempts_apart_from_requests():
    report = ApiUsageReport("validate")
    with collect_api_usage(report.total):
        recorder = RequestRecorder("rest", RequestStatistics())
        recorder.record(RequestOutcome("GET /orgs/{org}/members"))
        recorder._record_unsent_attempt("timeout")
        recorder._record_unsent_attempt("timeout")
        recorder._record_unsent_attempt("interrupted")
    report.finish("completed")

    console = Console(record=True, width=120)
    report.print(console)
    output = console.export_text()
    data = report.to_json()

    assert "Not sent:    timeout: 2 · interrupted: 1 (failed before being sent, not counted as requests)" in output
    assert data["total"]["requests"] == 1
    assert data["total"]["errors"] == {}
    assert data["apis"]["rest"]["unsent_attempts"] == {"interrupted": 1, "timeout": 2}


def test_every_graphql_query_reports_its_cost():
    queries = [x for x in files(resources).joinpath("graphql").iterdir() if x.name.endswith(".gql")]
    assert len(queries) > 0

    for query in queries:
        content = query.read_text()
        assert "rateLimit {" in content, f"query '{query.name}' does not ask for its rateLimit"
        assert "cost" in content, f"query '{query.name}' does not report its cost"


async def test_redirect_waiting_for_a_connection_is_not_sent():
    recorder = RequestRecorder("rest", RequestStatistics(), charge_responses=True)
    usage = ApiUsage()
    url = URL("https://api.github.com/repos/acme/website/zipball/main")
    context = SimpleNamespace(trace_request_ctx={"current_attempt": 1})

    def params(**kwargs):
        return pretend.stub(method="GET", url=url, **kwargs)

    # emits the trace events of aiohttp for a redirect, whose target times out waiting for a connection
    with collect_api_usage(usage):
        await recorder._on_request_start(None, context, params())
        await recorder._on_connection_obtained(None, context, params())
        await recorder._on_request_response(None, context, params(response=pretend.stub(status=302, headers={})))
        await recorder._on_request_exception(None, context, params(exception=TimeoutError()))

    assert usage.rest.total_requests == 1
    assert usage.rest.error_count == 0
    assert usage.rest.unsent_attempts == {"timeout": 1}


async def test_malformed_rate_limit_does_not_prevent_recording_the_request():
    recorder = RequestRecorder("rest", RequestStatistics(), charge_responses=True, default_resource="core")
    usage = ApiUsage()
    url = URL("https://api.github.com/orgs/acme")
    context = SimpleNamespace(trace_request_ctx={"current_attempt": 1})
    response = pretend.stub(status=200, headers={"x-ratelimit-remaining": "n/a"})

    with collect_api_usage(usage):
        await recorder._on_request_start(None, context, pretend.stub(method="GET", url=url))
        await recorder._on_request_response(None, context, pretend.stub(method="GET", url=url, response=response))

    assert usage.rest.total_requests == 1
    assert len(usage.rest.rate_limits) == 0
