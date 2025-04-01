#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import contextlib
import json
from asyncio import CancelledError
from typing import TYPE_CHECKING

from importlib_resources import files

from otterdog import resources
from otterdog.utils import get_logger, is_ghsa_repo, is_set_and_present

if TYPE_CHECKING:
    from typing import Any

    from otterdog.credentials import Credentials


_ORG_SETTINGS_SCHEMA = json.loads(files(resources).joinpath("schemas/settings.json").read_text())

# collect supported rest api keys
_SETTINGS_RESTAPI_KEYS = {k for k, v in _ORG_SETTINGS_SCHEMA["properties"].items() if v.get("provider") == "restapi"}
# collect supported web interface keys
_SETTINGS_WEB_KEYS = {k for k, v in _ORG_SETTINGS_SCHEMA["properties"].items() if v.get("provider") == "web"}
# TODO: make this cleaner
_SETTINGS_WEB_KEYS.add("discussion_source_repository_id")

_logger = get_logger(__name__)


def is_org_settings_key_retrieved_via_web_ui(key: str) -> bool:
    return key in _SETTINGS_WEB_KEYS


class GitHubProvider:
    def __init__(self, credentials: Credentials | None):
        self._credentials = credentials

        if credentials is not None:
            self._init_clients()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exception_type, exception_value, exception_traceback):
        await self.close()

    async def close(self) -> None:
        if self._credentials is not None:
            with contextlib.suppress(CancelledError):
                await self.rest_api.close()

            with contextlib.suppress(CancelledError):
                await self.graphql_client.close()

    def _init_clients(self):
        from otterdog.cache import get_github_cache
        from otterdog.providers.github.auth import token_auth

        from .graphql import GraphQLClient
        from .rest import RestApi
        from .web import WebClient

        self.rest_api = RestApi(token_auth(self._credentials.github_token), get_github_cache())
        self.web_client = WebClient(self._credentials)
        self.graphql_client = GraphQLClient(token_auth(self._credentials.github_token), get_github_cache())

    async def get_content(self, org_id: str, repo_name: str, path: str, ref: str | None = None) -> str:
        return await self.rest_api.content.get_content(org_id, repo_name, path, ref)

    async def update_content(
        self,
        org_id: str,
        repo_name: str,
        path: str,
        content: str,
        ref: str | None = None,
        message: str | None = None,
        author_name: str | None = None,
        author_email: str | None = None,
    ) -> bool:
        return await self.rest_api.content.update_content(
            org_id,
            repo_name,
            path,
            content,
            ref,
            message,
            author_name,
            author_email,
        )

    async def get_org_settings(
        self,
        org_id: str,
        included_keys: set[str],
        no_web_ui: bool,
    ) -> dict[str, Any]:
        # first, get supported settings via the rest api.
        required_rest_keys = {x for x in included_keys if x in _SETTINGS_RESTAPI_KEYS}
        merged_settings = await self.rest_api.org.get_settings(org_id, required_rest_keys)

        # second, get settings only accessible via the web interface and merge
        # them with the other settings, unless --no-web-ui is specified.
        if not no_web_ui:
            required_web_keys = {x for x in included_keys if x in _SETTINGS_WEB_KEYS}
            if len(required_web_keys) > 0:
                web_settings = await self.web_client.get_org_settings(org_id, required_web_keys)
                merged_settings.update(web_settings)

            _logger.trace(f"merged org settings = {merged_settings}")

        return merged_settings

    async def update_org_settings(self, org_id: str, settings: dict[str, Any]) -> None:
        rest_fields = {}
        web_fields = {}

        # split up settings to be updated whether they need be updated
        # via rest api or web interface.
        for k, v in sorted(settings.items()):
            if k in _SETTINGS_RESTAPI_KEYS:
                rest_fields[k] = v
            elif k in _SETTINGS_WEB_KEYS:
                web_fields[k] = v
            else:
                _logger.warning(f"encountered unknown field '{k}' during update, ignoring")

        # update any settings via the rest api
        if len(rest_fields) > 0:
            await self.rest_api.org.update_settings(org_id, rest_fields)

        # update any settings via the web interface
        if len(web_fields) > 0:
            await self.web_client.update_org_settings(org_id, web_fields)

    async def get_org_workflow_settings(self, org_id: str) -> dict[str, Any]:
        return await self.rest_api.org.get_workflow_settings(org_id)

    async def update_org_workflow_settings(self, org_id: str, workflow_settings: dict[str, Any]) -> None:
        await self.rest_api.org.update_workflow_settings(org_id, workflow_settings)

    async def get_org_custom_roles(self, org_id: str) -> list[dict[str, Any]]:
        return await self.rest_api.org.get_custom_roles(org_id)

    async def add_org_custom_role(self, org_id: str, role_name: str, data: dict[str, str]) -> None:
        await self.rest_api.org.add_custom_role(org_id, role_name, data)

    async def update_org_custom_role(self, org_id: str, role_id: int, role_name: str, data: dict[str, str]) -> None:
        await self.rest_api.org.update_custom_role(org_id, role_id, role_name, data)

    async def delete_org_custom_role(self, org_id: str, role_id: int, role_name: str) -> None:
        await self.rest_api.org.delete_custom_role(org_id, role_id, role_name)

    async def get_org_teams(self, org_id: str) -> list[dict[str, Any]]:
        return await self.rest_api.team.get_teams(org_id)

    async def get_org_team_members(self, org_id: str, team_slug: str) -> list[dict[str, Any]]:
        return await self.rest_api.team.get_team_members(org_id, team_slug)

    async def add_org_team(self, org_id: str, team_name: str, data: dict[str, str]) -> None:
        await self.rest_api.team.add_team(org_id, team_name, data)

    async def update_org_team(self, org_id: str, team_slug: str, team_name: str, data: dict[str, str]) -> None:
        if not is_set_and_present(team_slug):
            team_slug = await self.rest_api.team.get_team_slug(org_id, team_name)

        await self.rest_api.team.update_team(org_id, team_slug, data)

    async def delete_org_team(self, org_id: str, team_slug: str) -> None:
        await self.rest_api.team.delete_team(org_id, team_slug)

    async def get_org_custom_properties(self, org_id: str) -> list[dict[str, Any]]:
        return await self.rest_api.org.get_custom_properties(org_id)

    async def add_org_custom_property(self, org_id: str, property_name: str, data: dict[str, str]) -> None:
        await self.rest_api.org.add_custom_property(org_id, property_name, data)

    async def update_org_custom_property(self, org_id: str, property_name: str, data: dict[str, str]) -> None:
        await self.rest_api.org.update_custom_property(org_id, property_name, data)

    async def delete_org_custom_property(self, org_id: str, property_name: str) -> None:
        await self.rest_api.org.delete_custom_property(org_id, property_name)

    async def get_org_webhooks(self, org_id: str) -> list[dict[str, Any]]:
        return await self.rest_api.org.get_webhooks(org_id)

    async def update_org_webhook(self, org_id: str, webhook_id: int, url: str, webhook: dict[str, Any]) -> None:
        if len(webhook) > 0:
            if not is_set_and_present(webhook_id):
                webhook_id = await self.rest_api.org.get_webhook_id(org_id, url)

            await self.rest_api.org.update_webhook(org_id, webhook_id, webhook)

    async def add_org_webhook(self, org_id: str, data: dict[str, str]) -> None:
        await self.rest_api.org.add_webhook(org_id, data)

    async def delete_org_webhook(self, org_id: str, webhook_id: int, url: str) -> None:
        if not is_set_and_present(webhook_id):
            webhook_id = await self.rest_api.org.get_webhook_id(org_id, url)

        await self.rest_api.org.delete_webhook(org_id, webhook_id, url)

    async def get_org_rulesets(self, org_id: str) -> list[dict[str, Any]]:
        return await self.rest_api.org.get_rulesets(org_id)

    async def update_org_ruleset(self, org_id: str, ruleset_id: int, name: str, ruleset: dict[str, Any]) -> None:
        if len(ruleset) > 0:
            if not is_set_and_present(ruleset_id):
                ruleset_id = await self.rest_api.org.get_ruleset_id(org_id, name)

            await self.rest_api.org.update_ruleset(org_id, ruleset_id, ruleset)

    async def add_org_ruleset(self, org_id: str, data: dict[str, str]) -> None:
        await self.rest_api.org.add_ruleset(org_id, data)

    async def delete_org_ruleset(self, org_id: str, ruleset_id: int, name: str) -> None:
        if not is_set_and_present(ruleset_id):
            ruleset_id = await self.rest_api.org.get_ruleset_id(org_id, name)

        await self.rest_api.org.delete_ruleset(org_id, ruleset_id, name)

    async def get_repos(self, org_id: str) -> list[str]:
        # filter out repos which are created to work on GitHub Security Advisories
        # they should not be part of the visible configuration
        return list(filter(lambda name: not is_ghsa_repo(name), await self.rest_api.org.get_repos(org_id)))

    async def get_repo_data(self, org_id: str, repo_name: str) -> dict[str, Any]:
        return await self.rest_api.repo.get_repo_data(org_id, repo_name)

    async def get_repo_by_id(self, repo_id: int) -> dict[str, Any]:
        return await self.rest_api.repo.get_repo_by_id(repo_id)

    async def update_repo(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        if len(data) > 0:
            await self.rest_api.repo.update_repo(org_id, repo_name, data)

    async def add_repo(
        self,
        org_id: str,
        data: dict[str, str],
        template_repository: str | None,
        post_process_template_content: list[str],
        forked_repository: str | None,
        fork_default_branch_only: bool,
        auto_init_repo: bool,
    ) -> None:
        await self.rest_api.repo.add_repo(
            org_id,
            data,
            template_repository,
            post_process_template_content,
            forked_repository,
            fork_default_branch_only,
            auto_init_repo,
        )

    async def delete_repo(self, org_id: str, repo_name: str) -> None:
        await self.rest_api.repo.delete_repo(org_id, repo_name)

    async def get_branch_protection_rules(self, org_id: str, repo: str) -> list[dict[str, Any]]:
        return await self.graphql_client.get_branch_protection_rules(org_id, repo)

    async def update_branch_protection_rule(
        self,
        org_id: str,
        repo_name: str,
        rule_id: str,
        rule_pattern: str,
        data: dict[str, Any],
    ) -> None:
        if not is_set_and_present(rule_id):
            rule_id = await self.graphql_client.get_branch_protection_rule_id(org_id, repo_name, rule_pattern)

        await self.graphql_client.update_branch_protection_rule(org_id, repo_name, rule_pattern, rule_id, data)

    async def add_branch_protection_rule(
        self,
        org_id: str,
        repo_name: str,
        repo_node_id: str | None,
        data: dict[str, Any],
    ) -> None:
        # in case the repo_id is not available yet, we need to fetch it from GitHub.
        if not is_set_and_present(repo_node_id):
            repo_data = await self.rest_api.repo.get_simple_repo_data(org_id, repo_name)
            repo_node_id = repo_data["node_id"]

        await self.graphql_client.add_branch_protection_rule(org_id, repo_name, repo_node_id, data)

    async def delete_branch_protection_rule(
        self,
        org_id: str,
        repo_name: str,
        rule_id: str,
        rule_pattern: str,
    ) -> None:
        if not is_set_and_present(rule_id):
            rule_id = await self.graphql_client.get_branch_protection_rule_id(org_id, repo_name, rule_pattern)

        await self.graphql_client.delete_branch_protection_rule(org_id, repo_name, rule_pattern, rule_id)

    async def update_repo_ruleset(
        self, org_id: str, repo_name: str, ruleset_id: int, name: str, ruleset: dict[str, Any]
    ) -> None:
        if len(ruleset) > 0:
            if not is_set_and_present(ruleset_id):
                ruleset_id = await self.rest_api.repo.get_ruleset_id(org_id, repo_name, name)

            await self.rest_api.repo.update_ruleset(org_id, repo_name, ruleset_id, ruleset)

    async def add_repo_ruleset(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        await self.rest_api.repo.add_ruleset(org_id, repo_name, data)

    async def delete_repo_ruleset(self, org_id: str, repo_name: str, ruleset_id: int, name: str) -> None:
        if not is_set_and_present(ruleset_id):
            ruleset_id = await self.rest_api.repo.get_ruleset_id(org_id, repo_name, name)

        await self.rest_api.repo.delete_ruleset(org_id, repo_name, ruleset_id, name)

    async def get_repo_webhooks(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        return await self.rest_api.repo.get_webhooks(org_id, repo_name)

    async def update_repo_webhook(
        self, org_id: str, repo_name: str, webhook_id: int, url: str, webhook: dict[str, Any]
    ) -> None:
        if len(webhook) > 0:
            if not is_set_and_present(webhook_id):
                webhook_id = await self.rest_api.repo.get_webhook_id(org_id, repo_name, url)

            await self.rest_api.repo.update_webhook(org_id, repo_name, webhook_id, webhook)

    async def add_repo_webhook(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        await self.rest_api.repo.add_webhook(org_id, repo_name, data)

    async def delete_repo_webhook(self, org_id: str, repo_name: str, webhook_id: int, url: str) -> None:
        if not is_set_and_present(webhook_id):
            webhook_id = await self.rest_api.repo.get_webhook_id(org_id, repo_name, url)

        await self.rest_api.repo.delete_webhook(org_id, repo_name, webhook_id, url)

    async def get_repo_environments(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        return await self.rest_api.repo.get_environments(org_id, repo_name)

    async def update_repo_environment(self, org_id: str, repo_name: str, env_name: str, env: dict[str, Any]) -> None:
        if len(env) > 0:
            await self.rest_api.repo.update_environment(org_id, repo_name, env_name, env)

    async def add_repo_environment(self, org_id: str, repo_name: str, env_name: str, data: dict[str, str]) -> None:
        await self.rest_api.repo.add_environment(org_id, repo_name, env_name, data)

    async def delete_repo_environment(self, org_id: str, repo_name: str, env_name: str) -> None:
        await self.rest_api.repo.delete_environment(org_id, repo_name, env_name)

    async def get_repo_workflow_settings(self, org_id: str, repo_name: str) -> dict[str, Any]:
        return await self.rest_api.repo.get_workflow_settings(org_id, repo_name)

    async def update_repo_workflow_settings(
        self, org_id: str, repo_name: str, workflow_settings: dict[str, Any]
    ) -> None:
        await self.rest_api.repo.update_workflow_settings(org_id, repo_name, workflow_settings)

    async def get_org_secrets(self, org_id: str) -> list[dict[str, Any]]:
        return await self.rest_api.org.get_secrets(org_id)

    async def update_org_secret(self, org_id: str, secret_name: str, secret: dict[str, Any]) -> None:
        if len(secret) > 0:
            await self.rest_api.org.update_secret(org_id, secret_name, secret)

    async def add_org_secret(self, org_id: str, data: dict[str, str]) -> None:
        await self.rest_api.org.add_secret(org_id, data)

    async def delete_org_secret(self, org_id: str, secret_name: str) -> None:
        await self.rest_api.org.delete_secret(org_id, secret_name)

    async def get_org_variables(self, org_id: str) -> list[dict[str, Any]]:
        return await self.rest_api.org.get_variables(org_id)

    async def update_org_variable(self, org_id: str, variable_name: str, variable: dict[str, Any]) -> None:
        if len(variable) > 0:
            await self.rest_api.org.update_variable(org_id, variable_name, variable)

    async def add_org_variable(self, org_id: str, data: dict[str, str]) -> None:
        await self.rest_api.org.add_variable(org_id, data)

    async def delete_org_variable(self, org_id: str, variable_name: str) -> None:
        await self.rest_api.org.delete_variable(org_id, variable_name)

    async def get_repo_secrets(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        return await self.rest_api.repo.get_secrets(org_id, repo_name)

    async def update_repo_secret(self, org_id: str, repo_name: str, secret_name: str, secret: dict[str, Any]) -> None:
        if len(secret) > 0:
            await self.rest_api.repo.update_secret(org_id, repo_name, secret_name, secret)

    async def add_repo_secret(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        await self.rest_api.repo.add_secret(org_id, repo_name, data)

    async def delete_repo_secret(self, org_id: str, repo_name: str, secret_name: str) -> None:
        await self.rest_api.repo.delete_secret(org_id, repo_name, secret_name)

    async def get_repo_variables(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        return await self.rest_api.repo.get_variables(org_id, repo_name)

    async def update_repo_variable(
        self, org_id: str, repo_name: str, variable_name: str, variable: dict[str, Any]
    ) -> None:
        if len(variable) > 0:
            await self.rest_api.repo.update_variable(org_id, repo_name, variable_name, variable)

    async def add_repo_variable(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        await self.rest_api.repo.add_variable(org_id, repo_name, data)

    async def delete_repo_variable(self, org_id: str, repo_name: str, variable_name: str) -> None:
        await self.rest_api.repo.delete_variable(org_id, repo_name, variable_name)

    async def dispatch_workflow(self, org_id: str, repo_name: str, workflow_name: str) -> bool:
        return await self.rest_api.repo.dispatch_workflow(org_id, repo_name, workflow_name)

    async def get_repo_ids(self, org_id: str, repo_names: list[str]) -> list[str]:
        repo_ids = []
        for repo_name in repo_names:
            repo_data = await self.rest_api.repo.get_simple_repo_data(org_id, repo_name)
            repo_ids.append(repo_data["id"])
        return repo_ids

    async def get_actor_node_ids(self, actor_names: list[str]) -> list[str]:
        return [x[1][1] for x in await self.get_actor_ids_with_type(actor_names)]

    async def get_actor_ids_with_type(self, actor_names: list[str]) -> list[tuple[str, tuple[int, str]]]:
        result = []
        for actor in actor_names:
            if actor.startswith("@"):
                # if it starts with a @, it's either a user or team:
                #    - team-names contains a / in its slug
                #    - user-names are not allowed to contain a /
                if "/" in actor:
                    try:
                        result.append(("Team", await self.rest_api.team.get_team_ids(actor[1:])))
                    except RuntimeError:
                        _logger.warning(f"team '{actor[1:]}' does not exist, skipping")
                else:
                    try:
                        result.append(("User", await self.rest_api.user.get_user_ids(actor[1:])))
                    except RuntimeError:
                        _logger.warning(f"user '{actor[1:]}' does not exist, skipping")
            else:
                # it's an app
                try:
                    result.append(("App", await self.rest_api.app.get_app_ids(actor)))
                except RuntimeError:
                    _logger.warning(f"app '{actor}' does not exist, skipping")

        return result

    async def get_app_node_ids(self, app_names: set[str]) -> dict[str, str]:
        return {app_name: (await self.rest_api.app.get_app_ids(app_name))[1] for app_name in app_names}

    async def get_app_ids(self, app_names: set[str]) -> dict[str, str]:
        return {app_name: (await self.rest_api.app.get_app_ids(app_name))[0] for app_name in app_names}

    async def get_ref_for_pull_request(self, org_id: str, repo_name: str, pull_number: str) -> str:
        return await self.rest_api.repo.get_ref_for_pull_request(org_id, repo_name, pull_number)
