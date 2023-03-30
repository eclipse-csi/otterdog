# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
from typing import Any

import jq
from importlib_resources import files

import requests

from . import resources
from . import utils


class GithubGraphQL:
    _GH_GRAPHQL_URL_ROOT = "https://api.github.com/graphql"

    def __init__(self, token: str):
        self._token = token

        self._headers = {
            "Authorization": f"Bearer {token}",
        }

    def get_branch_protection_rules(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        utils.print_debug(f"retrieving branch protection rules for repo '{repo_name}' via graphql API")

        variables = {"organization": org_id, "repository": repo_name}
        branch_protection_rules = self._run_paged_query(variables, "get-branch-protection-rules.gql")

        for branch_protection_rule in branch_protection_rules:
            variables = {"branchProtectionRuleId": branch_protection_rule["id"]}
            pushAllowanceActors = \
                self._run_paged_query(variables, "get-push-allowances.gql", ".data.node.pushAllowances")
            branch_protection_rule["pushRestrictions"] = self._transform_actors(pushAllowanceActors)

            reviewDismissalAllowanceActors = \
                self._run_paged_query(variables,
                                      "get-review-dismissal-allowances.gql",
                                      ".data.node.reviewDismissalAllowances")
            branch_protection_rule["reviewDismissalAllowances"] = \
                self._transform_actors(reviewDismissalAllowanceActors)

        return branch_protection_rules

    def update_branch_protection_rule(self,
                                      org_id: str,
                                      repo_name: str,
                                      rule_pattern: str,
                                      rule_id: str,
                                      data: dict[str, Any]) -> None:
        utils.print_debug(f"updating branch protection rule '{rule_pattern}' for repo '{repo_name}' via graphql API")

        data["branchProtectionRuleId"] = rule_id
        variables = {"ruleInput": data}

        query = """mutation($ruleInput: UpdateBranchProtectionRuleInput!) {
           updateBranchProtectionRule(input:$ruleInput) {
             branchProtectionRule {
               pattern
             }
           }  
        }"""

        response = requests.post(url=f"{self._GH_GRAPHQL_URL_ROOT}",
                                 headers=self._headers,
                                 json={"query": query, "variables": variables})
        utils.print_trace(f"rest result = ({response.status_code}, {response.text})")

        if not response.ok:
            msg = f"failed updating branch protection rule '{rule_pattern}' for repo '{repo_name}' via graphql"
            raise RuntimeError(msg)

        json_data = response.json()
        if "data" in json_data:
            utils.print_debug(f"successfully updated branch protection rule '{rule_pattern}' via graphql")
        else:
            raise RuntimeError(f"failed to update branch protection rule '{rule_pattern}' via graphql")

    def add_branch_protection_rule(self, org_id: str, repo_name: str, repo_id: str, data: dict[str, Any]) -> None:
        rule_pattern = data["pattern"]
        utils.print_debug(f"creating branch_protection_rule with pattern '{rule_pattern}'"
                          f"for repo '{repo_name}' via rest API")

        data["repositoryId"] = repo_id
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

        response = requests.post(url=f"{self._GH_GRAPHQL_URL_ROOT}",
                                 headers=self._headers,
                                 json={"query": query, "variables": variables})
        utils.print_trace(f"rest result = ({response.status_code}, {response.text})")

        if not response.ok:
            msg = f"failed creating branch protection rule '{rule_pattern}' for repo '{repo_name}' via graphql"
            raise RuntimeError(msg)

        json_data = response.json()
        if "data" in json_data:
            utils.print_debug(f"successfully created branch protection rule '{rule_pattern}' via graphql")
        else:
            raise RuntimeError(f"failed to create branch protection rule '{rule_pattern}' via graphql")

    def _run_paged_query(self,
                         input_variables: dict[str, str],
                         query_file: str,
                         prefix_selector: str = ".data.repository.branchProtectionRules") -> list[dict[str, Any]]:
        utils.print_debug(f"running graphql query '{query_file}' with input '{json.dumps(input_variables)}'")

        query = files(resources).joinpath(query_file).read_text()

        finished = False
        end_cursor = None
        result = []

        while not finished:
            variables = {"endCursor": end_cursor}
            variables.update(input_variables)

            response = requests.post(url=f"{self._GH_GRAPHQL_URL_ROOT}",
                                     headers=self._headers,
                                     json={"query": query, "variables": variables})
            utils.print_trace(f"rest result = ({response.status_code}, {response.text})")

            if not response.ok:
                raise RuntimeError(f"failed running query '{query_file}' via graphql")

            json_data = response.json()
            if "data" in json_data:
                rules_result =\
                    jq.compile(prefix_selector + ".nodes")\
                      .input(json_data)\
                      .first()

                for rule in rules_result:
                    result.append(rule)

                page_info =\
                    jq.compile(prefix_selector + ".pageInfo")\
                      .input(json_data)\
                      .first()

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
                result.append(f"/{login}")
            elif typename == "Team":
                slug = actor["combinedSlug"]
                result.append(slug)
            else:
                raise RuntimeError(f"unsupported actor '{actor}'")

        return result
