# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os
from typing import Any

import schemas
import utils
from bitwarden import Credentials
from github_graphql import GithubGraphQL
from github_rest import GithubRest
from github_web import GithubWeb


class Github:
    def __init__(self, credentials: Credentials):
        self.credentials = credentials
        os.environ["GH_TOKEN"] = credentials.github_token

        settings_schema = schemas.SETTINGS_SCHEMA
        # collect supported rest api keys
        self.settings_restapi_keys =\
            {k for k, v in settings_schema["properties"].items() if v.get("provider") == "restapi"}

        # collect supported web interface keys
        self.settings_web_keys =\
            {k for k, v in settings_schema["properties"].items() if v.get("provider") == "web"}

        self.rest_client = GithubRest(credentials.github_token)
        self.web_client = GithubWeb(self.credentials)
        self.graphql_client = GithubGraphQL(credentials.github_token)

    def get_org_settings(self, org_id: str, included_keys: set[str]) -> dict[str, str]:
        # first, get supported settings via the rest api.
        required_rest_keys = {x for x in included_keys if x in self.settings_restapi_keys}
        merged_settings = self.rest_client.get_org_settings(org_id, required_rest_keys)

        # second, get settings only accessible via the web interface and merge
        # them with the other settings.
        required_web_keys = {x for x in included_keys if x in self.settings_web_keys}
        if len(required_web_keys) > 0:
            web_settings = self.web_client.get_org_settings(org_id, required_web_keys)
            merged_settings.update(web_settings)

        utils.print_trace(f"merged org settings = {merged_settings}")
        return merged_settings

    def update_org_settings(self, org_id: str, settings: dict[str, str]) -> None:
        rest_fields = {}
        web_fields = {}

        # split up settings to be updated whether they need be updated
        # via rest api or web interface.
        for k, v in sorted(settings.items()):
            if k in self.settings_restapi_keys:
                rest_fields[k] = v
            elif k in self.settings_web_keys:
                web_fields[k] = v
            else:
                utils.print_warn(f"encountered unknown field '{k}' during update, ignoring")

        # update any settings via the rest api
        if len(rest_fields) > 0:
            self.rest_client.update_org_settings(org_id, rest_fields)

        # update any settings via the web interface
        if len(web_fields) > 0:
            self.web_client.update_org_settings(org_id, web_fields)

    def get_webhooks(self, org_id: str) -> list[dict[str, Any]]:
        return self.rest_client.get_webhooks(org_id)

    def update_webhook_config(self, org_id: str, webhook_id: str, config: dict[str, str]) -> None:
        if len(config) > 0:
            self.rest_client.update_webhook_config(org_id, webhook_id, config)

    def add_webhook(self, org_id: str, data: dict[str, str]) -> None:
        self.rest_client.add_webhook(org_id, data)

    def get_repos(self, org_id: str) -> list[str]:
        return self.rest_client.get_repos(org_id)

    def get_repo_data(self, org_id: str, repo_name: str) -> dict[str, Any]:
        return self.rest_client.get_repo_data(org_id, repo_name)

    def update_repo(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        if len(data) > 0:
            self.rest_client.update_repo(org_id, repo_name, data)

    def add_repo(self, org_id: str, data: dict[str, str]) -> None:
        self.rest_client.add_repo(org_id, data)

    def get_branch_protection_rules(self, org_id: str, repo: str) -> list[dict[str, Any]]:
        return self.graphql_client.get_branch_protection_rules(org_id, repo)

    def update_branch_protection_rule(self,
                                      org_id: str,
                                      repo_name: str,
                                      rule_pattern: str,
                                      rule_id: str,
                                      data: dict[str, Any]) -> None:
        self.graphql_client.update_branch_protection_rule(org_id, repo_name, rule_pattern, rule_id, data)

    def add_branch_protection_rule(self, org_id: str, repo_name: str, repo_id: str, data: dict[str, Any]) -> None:
        self.graphql_client.add_branch_protection_rule(org_id, repo_name, repo_id, data)
