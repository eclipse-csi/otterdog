#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import json
from functools import cache
from typing import TYPE_CHECKING

from aiohttp.client import ClientSession, ClientTimeout, TCPConnector
from aiohttp_retry import ExponentialRetry, RetryClient

from otterdog.logging import get_logger, is_trace_enabled
from otterdog.providers.github.stats import RequestStatistics
from otterdog.utils import query_json

if TYPE_CHECKING:
    from typing import Any

    from otterdog.providers.github.auth import AuthStrategy
    from otterdog.providers.github.cache import CacheStrategy

_logger = get_logger(__name__)


class GraphQLClient:
    _GH_GRAPHQL_URL_ROOT = "api.github.com/graphql"

    def __init__(self, auth_strategy: AuthStrategy, cache_strategy: CacheStrategy | None = None):
        self._auth = auth_strategy.get_auth()

        self._headers = {
            "X-Github-Next-Global-ID": "1",
        }

        self._statistics = RequestStatistics()

        self._cache_strategy = cache_strategy

        if cache_strategy is not None and cache_strategy.is_external():
            self._base_url = cache_strategy.replace_base_url(f"https://{self._GH_GRAPHQL_URL_ROOT}")
            self._use_proxy = True
        else:
            self._base_url = f"https://{self._GH_GRAPHQL_URL_ROOT}"
            self._use_proxy = False

        self._session = ClientSession(
            timeout=ClientTimeout(connect=3, sock_connect=3),
            connector=TCPConnector(limit=10),
        )

        self._client = RetryClient(
            retry_options=ExponentialRetry(3, exceptions={Exception}),
            client_session=self._session,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exception_type, exception_value, exception_traceback):
        await self.close()

    async def close(self) -> None:
        await self._session.close()

    @property
    def statistics(self) -> RequestStatistics:
        return self._statistics

    async def get_branch_protection_rule_id(self, org_id: str, repo_name: str, pattern: str) -> str:
        _logger.debug(f"getting branch protection rule id for pattern '{pattern}' at repo '{org_id}/{repo_name}'")

        variables = {"organization": org_id, "repository": repo_name}
        branch_protection_rules = await self._run_paged_query(variables, "get-branch-protection-rule-ids.gql")

        for rule in branch_protection_rules:
            if rule["pattern"] == pattern:
                return rule["id"]

        raise RuntimeError(f"failed to find branch protection rule with pattern '{pattern}'")

    async def get_branch_protection_rules(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        _logger.debug(f"retrieving branch protection rules for repo '{org_id}/{repo_name}'")

        variables = {"organization": org_id, "repository": repo_name}
        branch_protection_rules = await self._run_paged_query(variables, "get-branch-protection-rules.gql")

        for branch_protection_rule in branch_protection_rules:
            await self._fill_paged_results_if_needed(
                branch_protection_rule,
                "pushAllowances",
                "pushRestrictions",
                "get-push-allowances.gql",
            )

            await self._fill_paged_results_if_needed(
                branch_protection_rule,
                "reviewDismissalAllowances",
                "reviewDismissalAllowances",
                "get-review-dismissal-allowances.gql",
            )

            await self._fill_paged_results_if_needed(
                branch_protection_rule,
                "bypassPullRequestAllowances",
                "bypassPullRequestAllowances",
                "get-bypass-pull-request-allowances.gql",
            )

            await self._fill_paged_results_if_needed(
                branch_protection_rule,
                "bypassForcePushAllowances",
                "bypassForcePushAllowances",
                "get-bypass-force-push-allowances.gql",
            )

        return branch_protection_rules

    async def _fill_paged_results_if_needed(
        self,
        branch_protection_rule: dict[str, Any],
        input_key: str,
        output_key: str,
        query_file: str,
    ):
        value = branch_protection_rule.pop(input_key)

        nodes = value["nodes"]
        all_actors = self._transform_actors(nodes)
        has_more = bool(query_json("pageInfo.hasNextPage", value) or False)

        if has_more is True:
            variables = {"branchProtectionRuleId": branch_protection_rule["id"]}
            more_actors = await self._run_paged_query(variables, query_file, f"data.node.{input_key}")
            all_actors.extend(self._transform_actors(more_actors))

        branch_protection_rule[output_key] = all_actors

    async def update_branch_protection_rule(
        self,
        org_id: str,
        repo_name: str,
        rule_pattern: str,
        rule_id: str,
        data: dict[str, Any],
    ) -> None:
        _logger.debug(f"updating branch protection rule '{rule_pattern}' for repo '{org_id}/{repo_name}'")

        data["branchProtectionRuleId"] = rule_id
        variables = {"ruleInput": data}

        query = """mutation($ruleInput: UpdateBranchProtectionRuleInput!) {
           updateBranchProtectionRule(input:$ruleInput) {
             branchProtectionRule {
               pattern
             }
           }
        }"""

        status, body = await self._request_raw("POST", query=query, variables=variables)
        if status >= 400:
            raise RuntimeError(
                f"failed updating branch protection rule '{rule_pattern}' for repo '{repo_name}': {body}"
            )

        json_data = json.loads(body)
        if "data" not in json_data:
            raise RuntimeError(f"failed to update branch protection rule '{rule_pattern}': {body}")

        _logger.debug(f"successfully updated branch protection rule '{rule_pattern}'")

    async def add_branch_protection_rule(
        self, org_id: str, repo_name: str, repo_node_id: str, data: dict[str, Any]
    ) -> None:
        rule_pattern = data["pattern"]
        _logger.debug(
            f"creating branch_protection_rule with pattern '{rule_pattern}' " f"for repo '{org_id}/{repo_name}'"
        )

        data["repositoryId"] = repo_node_id
        variables = {"ruleInput": data}

        query = """mutation($ruleInput: CreateBranchProtectionRuleInput!) {
           createBranchProtectionRule(input:$ruleInput) {
             branchProtectionRule {
               pattern
               blocksCreations
             }
           }
        }"""

        status, body = await self._request_raw("POST", query, variables)
        if status >= 400:
            raise RuntimeError(
                f"failed creating branch protection rule '{rule_pattern}' for repo '{repo_name}': {body}"
            )

        json_data = json.loads(body)
        if "data" not in json_data:
            raise RuntimeError(f"failed to create branch protection rule '{rule_pattern}': {body}")

        _logger.debug(f"successfully created branch protection rule '{rule_pattern}'")

    async def delete_branch_protection_rule(self, org_id: str, repo_name: str, rule_pattern: str, rule_id: str) -> None:
        _logger.debug(f"deleting branch protection rule '{rule_pattern}' for repo '{org_id}/{repo_name}'")

        variables = {"ruleInput": {"branchProtectionRuleId": rule_id}}

        query = """mutation($ruleInput: DeleteBranchProtectionRuleInput!) {
           deleteBranchProtectionRule(input:$ruleInput) {
             clientMutationId
           }
        }"""

        status, body = await self._request_raw("POST", query, variables)
        if status >= 400:
            raise RuntimeError(
                f"failed removing branch protection rule '{rule_pattern}' for repo '{repo_name}': {body}"
            )

        _logger.debug(f"successfully removed branch protection rule '{rule_pattern}'")

    async def get_issue_comments(self, org_id: str, repo_name: str, issue_number: int) -> list[dict[str, Any]]:
        _logger.debug(f"retrieving issue comments for issue '{org_id}/{repo_name}/#{issue_number}'")

        variables = {"owner": org_id, "repo": repo_name, "number": issue_number}
        issue_comments = await self._run_paged_query(
            variables, "get-issue-comments.gql", "data.repository.pullRequest.comments"
        )
        return issue_comments

    async def minimize_comment(self, comment_id: str, classifier: str) -> None:
        _logger.debug("minimizing comment")

        variables = {"input": {"subjectId": comment_id, "classifier": classifier}}

        query = """mutation($input: MinimizeCommentInput!) {
           minimizeComment(input: $input) {
             clientMutationId
           }
        }"""

        status, body = await self._request_raw("POST", query, variables)
        if status >= 400:
            raise RuntimeError(f"failed minimizing comment: {body}")

        _logger.debug("successfully minimized comment")

    async def get_team_membership(self, org_id: str, user_login: str) -> list[dict[str, Any]]:
        _logger.debug(f"retrieving team membership for user '{user_login}' in org '{org_id}'")

        variables = {"owner": org_id, "user": user_login}
        return await self._run_paged_query(variables, "get-team-membership.gql", "data.organization.teams")

    async def _run_paged_query(
        self,
        input_variables: dict[str, Any],
        query_file: str,
        prefix_selector: str = "data.repository.branchProtectionRules",
    ) -> list[dict[str, Any]]:
        _logger.debug(f"running graphql query '{query_file}' with input '{json.dumps(input_variables)}'")

        query = _get_query_from_file(query_file)

        finished = False
        end_cursor = None
        result = []

        while not finished:
            variables = {"endCursor": end_cursor}
            variables.update(input_variables)

            status, body = await self._request_raw("POST", query, variables)
            json_data = json.loads(body)

            if is_trace_enabled():
                _logger.trace("graphql result = %s", json.dumps(json_data, indent=2))

            if "data" in json_data:
                rules_result = query_json(prefix_selector + ".nodes", json_data)

                for rule in rules_result:
                    result.append(rule)

                page_info = query_json(prefix_selector + ".pageInfo", json_data)

                if page_info["hasNextPage"]:
                    end_cursor = page_info["endCursor"]
                else:
                    finished = True
            else:
                raise RuntimeError(f"failed running graphql query '{query_file}': {body}")

        return result

    async def _request_raw(self, method: str, query: str, variables: dict[str, Any]) -> tuple[int, str]:
        _logger.trace("'%s', query = %s, variables = %s", method, query[0:300] + "...", variables)

        headers = self._headers.copy()
        if self._auth is not None:
            self._auth.update_headers_with_authorization(headers)

        if self._cache_strategy is not None and self._use_proxy is True:
            kwargs = self._cache_strategy.get_request_parameters()
        else:
            kwargs = {}

        async with self._client.request(
            method,
            url=self._base_url,
            headers=headers,
            json={"query": query, "variables": variables},
            **kwargs,
        ) as response:
            self._statistics.sent_request()

            text = await response.text()
            status = response.status

            if status == 403 or status == 429:
                _logger.trace(f"graphql '{method}' result = ({status}, {text})")
                raise RuntimeError("failed running graphql query, hitting rate limit")

            self._statistics.update_remaining_rate_limit(int(response.headers.get("x-ratelimit-remaining", -1)))
            return status, text

    @staticmethod
    def _transform_actors(actors: list[dict[str, Any]]) -> list[str]:
        result = []
        for actor_wrapper in actors:
            actor = actor_wrapper["actor"]
            if actor is None:
                continue

            typename = actor["__typename"]
            if typename == "User":
                login = actor["login"]
                result.append(f"@{login}")
            elif typename == "Team":
                slug = actor["combinedSlug"]
                result.append(f"@{slug}")
            elif typename == "App":
                slug = actor["slug"]
                result.append(slug)
            else:
                raise RuntimeError(f"unsupported actor '{actor}'")

        return result


@cache
def _get_query_from_file(query_file: str) -> str:
    from importlib_resources import files

    from otterdog import resources

    return files(resources).joinpath(f"graphql/{query_file}").read_text()
