# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from typing import Any

from otterdog import schemas
from otterdog import utils
from otterdog.credentials import Credentials
from .graphql import GraphQLClient
from .rest import RestClient
from .web import WebClient


class Github:
    def __init__(self, credentials: Credentials):
        self._credentials = credentials

        self._settings_schema = schemas.SETTINGS_SCHEMA
        # collect supported rest api keys
        self._settings_restapi_keys =\
            {k for k, v in self._settings_schema["properties"].items() if v.get("provider") == "restapi"}

        # collect supported web interface keys
        self._settings_web_keys =\
            {k for k, v in self._settings_schema["properties"].items() if v.get("provider") == "web"}

        self._init_clients()

    def _init_clients(self):
        self.rest_client = RestClient(self._credentials.github_token)
        self.web_client = WebClient(self._credentials)
        self.graphql_client = GraphQLClient(self._credentials.github_token)

    def __getstate__(self):
        return self._credentials, self._settings_schema, self._settings_restapi_keys, self._settings_web_keys

    def __setstate__(self, state):
        self._credentials, self._settings_schema, self._settings_restapi_keys, self._settings_web_keys = state
        self._init_clients()

    @property
    def web_org_settings(self) -> set[str]:
        return self._settings_web_keys

    def is_web_org_setting(self, setting_key: str) -> bool:
        return setting_key in self._settings_web_keys

    def is_readonly_org_setting(self, setting_key: str) -> bool:
        setting_entry = self._settings_schema["properties"].get(setting_key)
        return setting_entry.get("readonly", False)

    def get_content(self, org_id: str, repo_name: str, path: str) -> str:
        return self.rest_client.get_content(org_id, repo_name, path)

    def update_content(self, org_id: str, repo_name: str, path: str, content: str, message: str = None) -> None:
        return self.rest_client.update_content(org_id, repo_name, path, content, message)

    def get_org_settings(self, org_id: str, included_keys: set[str]) -> dict[str, str]:
        # first, get supported settings via the rest api.
        required_rest_keys = {x for x in included_keys if x in self._settings_restapi_keys}
        merged_settings = self.rest_client.get_org_settings(org_id, required_rest_keys)

        # second, get settings only accessible via the web interface and merge
        # them with the other settings.
        required_web_keys = {x for x in included_keys if x in self._settings_web_keys}
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
            if k in self._settings_restapi_keys:
                rest_fields[k] = v
            elif k in self._settings_web_keys:
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

    def update_webhook(self, org_id: str, webhook_id: str, webhook: dict[str, Any]) -> None:
        if len(webhook) > 0:
            self.rest_client.update_webhook(org_id, webhook_id, webhook)

    def add_webhook(self, org_id: str, data: dict[str, str]) -> None:
        self.rest_client.add_webhook(org_id, data)

    def get_repos(self, org_id: str) -> list[str]:
        return self.rest_client.get_repos(org_id)

    def get_repo_data(self, org_id: str, repo_name: str) -> dict[str, Any]:
        return self.rest_client.get_repo_data(org_id, repo_name)

    def update_repo(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        if len(data) > 0:
            self.rest_client.update_repo(org_id, repo_name, data)

    def add_repo(self, org_id: str, data: dict[str, str], auto_init_repo: bool) -> None:
        self.rest_client.add_repo(org_id, data, auto_init_repo)

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
        # in case the repo_id is not available yet, we need to fetch it from GitHub.
        if not repo_id:
            repo_data = self.rest_client.get_repo_data(org_id, repo_name)
            repo_id = repo_data["node_id"]

        self.graphql_client.add_branch_protection_rule(org_id, repo_name, repo_id, data)

    def get_actor_ids(self, actor_names: list[str]) -> list[str]:
        result = []
        for actor in actor_names:
            if actor.startswith("/"):
                result.append(self.rest_client.get_user_node_id(actor[1:]))
            else:
                result.append(self.rest_client.get_team_node_id(actor))

        return result

    def get_app_ids(self, app_names: set[str]) -> dict[str, str]:
        return {app_name: self.rest_client.get_app_id(app_name) for app_name in app_names}
