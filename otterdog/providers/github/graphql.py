#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from typing import Any

import jq  # type: ignore
import requests
from aiohttp.client import ClientSession
from importlib_resources import files

from otterdog import resources, utils


class GraphQLClient:
    _GH_GRAPHQL_URL_ROOT = "https://api.github.com/graphql"

    def __init__(self, token: str):
        self._token = token

        self._headers = {
            "Authorization": f"Bearer {token}",
            "X-Github-Next-Global-ID": "1",
        }

    async def async_get_branch_protection_rules(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        utils.print_debug(f"async retrieving branch protection rules for repo '{org_id}/{repo_name}'")

        variables = {"organization": org_id, "repository": repo_name}
        branch_protection_rules = await self._async_run_paged_query(variables, "get-branch-protection-rules.gql")

        for branch_protection_rule in branch_protection_rules:
            await self._async_fill_paged_results_if_not_empty(
                branch_protection_rule,
                "pushAllowances",
                "pushRestrictions",
                "get-push-allowances.gql",
            )

            await self._async_fill_paged_results_if_not_empty(
                branch_protection_rule,
                "reviewDismissalAllowances",
                "reviewDismissalAllowances",
                "get-review-dismissal-allowances.gql",
            )

            await self._async_fill_paged_results_if_not_empty(
                branch_protection_rule,
                "bypassPullRequestAllowances",
                "bypassPullRequestAllowances",
                "get-bypass-pull-request-allowances.gql",
            )

            await self._async_fill_paged_results_if_not_empty(
                branch_protection_rule,
                "bypassForcePushAllowances",
                "bypassForcePushAllowances",
                "get-bypass-force-push-allowances.gql",
            )

        return branch_protection_rules

    async def _async_fill_paged_results_if_not_empty(
        self,
        branch_protection_rule: dict[str, Any],
        input_key: str,
        output_key: str,
        query_file: str,
    ):
        value = branch_protection_rule.pop(input_key)

        total_count = int(jq.compile(".totalCount").input(value).first())

        if total_count > 0:
            variables = {"branchProtectionRuleId": branch_protection_rule["id"]}
            actors = await self._async_run_paged_query(variables, query_file, f".data.node.{input_key}")
            branch_protection_rule[output_key] = self._transform_actors(actors)
        else:
            branch_protection_rule[output_key] = []

    def update_branch_protection_rule(
        self,
        org_id: str,
        repo_name: str,
        rule_pattern: str,
        rule_id: str,
        data: dict[str, Any],
    ) -> None:
        utils.print_debug(f"updating branch protection rule '{rule_pattern}' for repo '{org_id}/{repo_name}'")

        data["branchProtectionRuleId"] = rule_id
        variables = {"ruleInput": data}

        query = """mutation($ruleInput: UpdateBranchProtectionRuleInput!) {
           updateBranchProtectionRule(input:$ruleInput) {
             branchProtectionRule {
               pattern
             }
           }
        }"""

        response = requests.post(
            url=f"{self._GH_GRAPHQL_URL_ROOT}",
            headers=self._headers,
            json={"query": query, "variables": variables},
        )
        utils.print_trace(f"graphql result = ({response.status_code}, {response.text})")

        if not response.ok:
            msg = f"failed updating branch protection rule '{rule_pattern}' for repo '{repo_name}'"
            raise RuntimeError(msg)

        json_data = response.json()
        if "data" in json_data:
            utils.print_debug(f"successfully updated branch protection rule '{rule_pattern}'")
        else:
            raise RuntimeError(f"failed to update branch protection rule '{rule_pattern}'")

    def add_branch_protection_rule(self, org_id: str, repo_name: str, repo_node_id: str, data: dict[str, Any]) -> None:
        rule_pattern = data["pattern"]
        utils.print_debug(
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

        utils.print_trace(query)
        utils.print_trace(json.dumps(variables))

        response = requests.post(
            url=f"{self._GH_GRAPHQL_URL_ROOT}",
            headers=self._headers,
            json={"query": query, "variables": variables},
        )
        utils.print_trace(f"graphql result = ({response.status_code}, {response.text})")

        if not response.ok:
            msg = f"failed creating branch protection rule '{rule_pattern}' for repo '{repo_name}'"
            raise RuntimeError(msg)

        json_data = response.json()
        if "data" in json_data:
            utils.print_debug(f"successfully created branch protection rule '{rule_pattern}'")
        else:
            raise RuntimeError(f"failed to create branch protection rule '{rule_pattern}'")

    def delete_branch_protection_rule(self, org_id: str, repo_name: str, rule_pattern: str, rule_id: str) -> None:
        utils.print_debug(f"deleting branch protection rule '{rule_pattern}' for repo '{org_id}/{repo_name}'")

        variables = {"ruleInput": {"branchProtectionRuleId": rule_id}}

        query = """mutation($ruleInput: DeleteBranchProtectionRuleInput!) {
           deleteBranchProtectionRule(input:$ruleInput) {
             clientMutationId
           }
        }"""

        response = requests.post(
            url=f"{self._GH_GRAPHQL_URL_ROOT}",
            headers=self._headers,
            json={"query": query, "variables": variables},
        )
        utils.print_trace(f"graphql result = ({response.status_code}, {response.text})")

        if not response.ok:
            msg = f"failed removing branch protection rule '{rule_pattern}' for repo '{repo_name}'"
            raise RuntimeError(msg)

        utils.print_debug(f"successfully removed branch protection rule '{rule_pattern}'")

    async def _async_run_paged_query(
        self,
        input_variables: dict[str, Any],
        query_file: str,
        prefix_selector: str = ".data.repository.branchProtectionRules",
    ) -> list[dict[str, Any]]:
        utils.print_debug(f"running async graphql query '{query_file}' with input '{json.dumps(input_variables)}'")

        query = files(resources).joinpath(f"graphql/{query_file}").read_text()

        finished = False
        end_cursor = None
        result = []

        while not finished:
            variables = {"endCursor": end_cursor}
            variables.update(input_variables)

            async with ClientSession() as session:
                async with session.post(
                    url=f"{self._GH_GRAPHQL_URL_ROOT}",
                    headers=self._headers,
                    json={"query": query, "variables": variables},
                ) as response:
                    if utils.is_debug_enabled():
                        utils.print_debug(
                            f"graphql query '{query_file}' with input '{json.dumps(input_variables)}': "
                            f"rate-limit-used = {response.headers.get('x-ratelimit-used', None)}"
                        )

                    if utils.is_trace_enabled():
                        utils.print_trace(f"graphql result = ({response.status}, {await response.text()})")

                    if not response.ok:
                        raise RuntimeError(f"failed running query '{query_file}'")

                    json_data = await response.json()

            if "data" in json_data:
                rules_result = jq.compile(prefix_selector + ".nodes").input(json_data).first()

                for rule in rules_result:
                    result.append(rule)

                page_info = jq.compile(prefix_selector + ".pageInfo").input(json_data).first()

                if page_info["hasNextPage"]:
                    end_cursor = page_info["endCursor"]
                else:
                    finished = True
            else:
                raise RuntimeError(f"failed running graphql query '{query_file}'")

        return result

    @staticmethod
    def _transform_actors(actors: list[dict[str, Any]]) -> list[str]:
        result = []
        for actor_wrapper in actors:
            actor = actor_wrapper["actor"]
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
