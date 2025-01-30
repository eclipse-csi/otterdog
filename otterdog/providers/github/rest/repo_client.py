#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import asyncio
import json
import os
import pathlib
import re
import tempfile
import zipfile
from typing import Any

import aiofiles
import chevron

from otterdog.logging import is_trace_enabled
from otterdog.providers.github.exception import GitHubException
from otterdog.providers.github.rest import RestApi, RestClient, encrypt_value
from otterdog.utils import (
    associate_by_key,
    get_logger,
    is_set_and_present,
    query_json,
)

_logger = get_logger(__name__)


class RepoClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_simple_repo_data(self, org_id: str, repo_name: str) -> dict[str, Any]:
        _logger.debug("retrieving simple repo data for '%s/%s'", org_id, repo_name)

        try:
            return await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving simple repo data for repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def get_default_branch(self, org_id: str, repo_name: str) -> str:
        _logger.debug("retrieving default branch for repo '%s/%s'", org_id, repo_name)

        repo_data = await self.get_simple_repo_data(org_id, repo_name)
        return repo_data["default_branch"]

    async def get_branch(self, org_id: str, repo_name: str, branch_name: str) -> dict[str, Any]:
        _logger.debug("retrieving data for branch '%s' in repo '%s/%s'", branch_name, org_id, repo_name)

        try:
            return await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/branches/{branch_name}")
        except GitHubException as ex:
            raise RuntimeError(
                f"failed retrieving data for branch '{branch_name}' in repo '{org_id}/{repo_name}':\n{ex}"
            ) from ex

    async def rename_branch(self, org_id: str, repo_name: str, branch: str, new_name: str) -> dict[str, Any]:
        _logger.debug("renaming branch '%s' to '%s' in repo '%s/%s'", branch, new_name, org_id, repo_name)

        try:
            data = {"new_name": new_name}
            return await self.requester.request_json(
                "POST", f"/repos/{org_id}/{repo_name}/branches/{branch}/rename", data
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed renaming branch '{branch}' in repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def get_repo_data(self, org_id: str, repo_name: str) -> dict[str, Any]:
        _logger.debug("retrieving repo data for '%s/%s'", org_id, repo_name)

        try:
            repo_data = await self.get_simple_repo_data(org_id, repo_name)

            archived = repo_data.get("archived", False)
            if not archived:
                await self._fill_vulnerability_alerts(org_id, repo_name, repo_data)

                private = repo_data.get("private", False)
                if not private:
                    await self._fill_private_vulnerability_reporting(org_id, repo_name, repo_data)

            await self._fill_github_pages_config(org_id, repo_name, repo_data)
            await self._fill_topics(org_id, repo_name, repo_data)
            await self._fill_code_scanning_config(org_id, repo_name, repo_data)
            await self._fill_custom_properties(org_id, repo_name, repo_data)

            return repo_data
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving data for repo '{repo_name}':\n{ex}") from ex

    async def get_repo_by_id(self, repo_id: int) -> dict[str, Any]:
        _logger.debug("retrieving repo by id for '%d'", repo_id)

        try:
            return await self.requester.request_json("GET", f"/repositories/{repo_id}")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving data for repo '{repo_id}':\n{ex}") from ex

    async def update_repo(self, org_id: str, repo_name: str, data: dict[str, Any]) -> None:
        _logger.debug("updating repo settings for repo '%s/%s'", org_id, repo_name)

        changes = len(data)

        if "dependabot_alerts_enabled" in data:
            vulnerability_alerts = bool(data.pop("dependabot_alerts_enabled"))
        else:
            vulnerability_alerts = None

        if "private_vulnerability_reporting_enabled" in data:
            private_vulnerability_reporting = bool(data.pop("private_vulnerability_reporting_enabled"))
        else:
            private_vulnerability_reporting = None

        topics = list(data.pop("topics")) if "topics" in data else None
        custom_properties = list(data.pop("custom_properties")) if "custom_properties" in data else None
        gh_pages = data.pop("gh_pages") if "gh_pages" in data else None
        code_scanning = data.pop("code_scanning_default_config") if "code_scanning_default_config" in data else None
        default_branch = data.pop("default_branch") if "default_branch" in data else None

        if changes > 0:
            try:
                if len(data) > 0:
                    await self.requester.request_json("PATCH", f"/repos/{org_id}/{repo_name}", data)

                if vulnerability_alerts is not None:
                    await self._update_vulnerability_alerts(org_id, repo_name, vulnerability_alerts)
                if private_vulnerability_reporting is not None:
                    await self._update_private_vulnerability_reporting(
                        org_id, repo_name, private_vulnerability_reporting
                    )
                if topics is not None:
                    await self._update_topics(org_id, repo_name, topics)
                if custom_properties is not None and len(custom_properties) > 0:
                    await self._update_custom_properties(org_id, repo_name, custom_properties)
                if gh_pages is not None:
                    await self._update_github_pages_config(org_id, repo_name, gh_pages)
                if code_scanning is not None:
                    await self._update_code_scanning_config(org_id, repo_name, code_scanning)
                if default_branch is not None:
                    await self._update_default_branch(org_id, repo_name, default_branch)

                _logger.debug("updated %d repo setting(s) for repo '%s/%s'", changes, org_id, repo_name)
            except GitHubException as ex:
                raise RuntimeError(f"failed to update settings for repo '{repo_name}':\n{ex}") from ex

    async def add_repo(
        self,
        org_id: str,
        data: dict[str, Any],
        template_repository: str | None,
        post_process_template_content: list[str],
        forked_repository: str | None,
        fork_default_branch_only: bool,
        auto_init_repo: bool,
    ) -> None:
        repo_name = data["name"]

        if is_set_and_present(forked_repository):
            _logger.debug("forking repo '%s' to '%s/%s'", forked_repository, org_id, repo_name)
            upstream_owner, upstream_repo = re.split("/", forked_repository, maxsplit=1)

            try:
                fork_data = {
                    "organization": org_id,
                    "name": repo_name,
                    "default_branch_only": fork_default_branch_only,
                }

                await self.requester.request_json(
                    "POST",
                    f"/repos/{upstream_owner}/{upstream_repo}/forks",
                    fork_data,
                )

                # get all the data for the created repo to avoid setting values that can not be changed due
                # to defaults from the organization (like web_commit_signoff_required)
                current_data = await self.get_repo_data(org_id, repo_name)
                self._remove_already_active_settings(data, current_data)
                await self.update_repo(org_id, repo_name, data)

                _logger.debug("forked repo with name '%s' from repo '%s'", repo_name, forked_repository)
                return
            except GitHubException as ex:
                raise RuntimeError(f"failed to fork repo '{repo_name}' from repo '{forked_repository}':\n{ex}") from ex

        if is_set_and_present(template_repository):
            _logger.debug("creating repo '%s/%s' from template '%s'", org_id, repo_name, template_repository)
            template_owner, template_repo = re.split("/", template_repository, maxsplit=1)

            try:
                template_data = {
                    "owner": org_id,
                    "name": repo_name,
                    "include_all_branches": False,
                    "private": data.get("private", False),
                }

                await self.requester.request_json(
                    "POST",
                    f"/repos/{template_owner}/{template_repo}/generate",
                    template_data,
                )

                _logger.debug("created repo with name '%s' from template '%s'", repo_name, template_repository)

                # get all the data for the created repo to avoid setting values that can not be changed due
                # to defaults from the organization (like web_commit_signoff_required)
                current_data = await self.get_repo_data(org_id, repo_name)
                self._remove_already_active_settings(data, current_data)
                await self.update_repo(org_id, repo_name, data)

                # wait till the repo is initialized, this might take a while.
                if len(post_process_template_content) > 0:
                    initialized = False
                    for i in range(1, 11):
                        try:
                            await self.get_readme(org_id, repo_name)
                            initialized = True
                            break
                        except RuntimeError:
                            _logger.trace(f"waiting for repo '{org_id}/{repo_name}' to be initialized, try {i} of 10")
                            import time

                            time.sleep(1)

                    if initialized is False:
                        raise RuntimeError(
                            f"failed to create repo from template '{template_repository}': "
                            f"repo not initialized after 5s"
                        )

                # if there is template content which shall be post-processed,
                # use chevron to expand some variables that might be used there.
                for content_path in post_process_template_content:
                    content = await self.rest_api.content.get_content(org_id, repo_name, content_path, None)
                    updated_content = self._render_template_content(org_id, repo_name, content)
                    if content != updated_content:
                        await self.rest_api.content.update_content(org_id, repo_name, content_path, updated_content)

                return
            except GitHubException as ex:
                raise RuntimeError(f"failed to create repo from template '{template_repository}':\n{ex}") from ex

        _logger.debug("creating repo '%s/%s'", org_id, repo_name)

        # some settings do not seem to be set correctly during creation
        # collect them and update the repo after creation.
        update_keys = [
            "dependabot_alerts_enabled",
            "web_commit_signoff_required",
            "security_and_analysis",
            "topics",
            "gh_pages",
            "code_scanning_default_config",
            "custom_properties",
            "private_vulnerability_reporting_enabled",
        ]

        if auto_init_repo is True:
            update_keys.append("default_branch")

        update_data = {}

        for update_key in update_keys:
            if update_key in data:
                update_data[update_key] = data.pop(update_key)

        # whether the repo should be initialized with an empty README
        data["auto_init"] = auto_init_repo

        # if gh pages are disabled, do not try to update the config as it will fail
        if "gh_pages" in update_data:
            gh_pages = update_data.get("gh_pages", {})
            build_type = gh_pages.get("build_type")
            if build_type == "disabled":
                update_data.pop("gh_pages")

        try:
            result = await self.requester.request_json("POST", f"/orgs/{org_id}/repos", data)
            _logger.debug("created repo with name '%s'", repo_name)
            self._remove_already_active_settings(update_data, result)
            # let's wait a bit for the repo to be created.
            # in some cases, the repo can not be access yet via the REST API, resulting in 404 errors
            # we prevent that by adding an arbitrary sleep
            await asyncio.sleep(2)
            await self.update_repo(org_id, repo_name, update_data)
        except GitHubException as ex:
            raise RuntimeError(f"failed to add repo with name '{org_id}/{repo_name}':\n{ex}") from ex

    async def get_webhook_id(self, org_id: str, repo_name: str, url: str) -> str:
        _logger.debug("retrieving id for repo webhook with url '%s' for repo '%s/%s'", url, org_id, repo_name)

        webhooks = await self.get_webhooks(org_id, repo_name)

        has_wildcard_url = url.endswith("*")
        stripped_url = url.rstrip("*")

        for webhook in webhooks:
            webhook_url = webhook["config"]["url"]
            if (has_wildcard_url is True and webhook_url.startswith(stripped_url)) or webhook_url == url:
                return webhook["id"]

        raise RuntimeError(f"failed to find repo webhook with url '{url}'")

    async def get_webhooks(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving webhooks for repo '%s/%s'", org_id, repo_name)

        try:
            return await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/hooks")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving webhooks for repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def update_webhook(self, org_id: str, repo_name: str, webhook_id: int, webhook: dict[str, Any]) -> None:
        _logger.debug("updating repo webhook '%d' for repo '%s/%s'", webhook_id, org_id, repo_name)

        try:
            await self.requester.request_json("PATCH", f"/repos/{org_id}/{repo_name}/hooks/{webhook_id}", webhook)
            _logger.debug("updated repo webhook '%d'", webhook_id)
        except GitHubException as ex:
            raise RuntimeError(f"failed to update repo webhook {webhook_id}:\n{ex}") from ex

    async def add_webhook(self, org_id: str, repo_name: str, data: dict[str, Any]) -> None:
        url = data["config"]["url"]
        _logger.debug("adding repo webhook with url '%s' for repo '%s/%s'", url, org_id, repo_name)

        # mandatory field "name" = "web"
        data["name"] = "web"

        try:
            await self.requester.request_json("POST", f"/repos/{org_id}/{repo_name}/hooks", data)
            _logger.debug("added repo webhook with url '%s'", url)
        except GitHubException as ex:
            raise RuntimeError(f"failed to add repo webhook with url '{url}':\n{ex}") from ex

    async def delete_webhook(self, org_id: str, repo_name: str, webhook_id: int, url: str) -> None:
        _logger.debug("deleting repo webhook with url '%s' for repo '%s/%s'", url, org_id, repo_name)

        status, _ = await self.requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}/hooks/{webhook_id}")

        if status != 204:
            raise RuntimeError(f"failed to delete repo webhook with url '{url}'")

        _logger.debug("removed repo webhook with url '%s'", url)

    async def get_ruleset_id(self, org_id: str, repo_name: str, name: str) -> str:
        _logger.debug("retrieving id for repo ruleset with name '%s' for repo '%s/%s'", name, org_id, repo_name)

        rulesets = await self.get_rulesets(org_id, repo_name)

        for ruleset in rulesets:
            if ruleset["name"] == name:
                return ruleset["id"]

        raise RuntimeError(f"failed to find repo ruleset with name '{name}'")

    async def get_rulesets(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving rulesets for repo '%s/%s'", org_id, repo_name)

        try:
            result = []
            params = {"includes_parents": "false"}
            response = await self.requester.request_paged_json(
                "GET", f"/repos/{org_id}/{repo_name}/rulesets", params=params
            )
            for ruleset in response:
                result.append(await self.get_ruleset(org_id, repo_name, str(ruleset["id"])))
            return result
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving rulesets for repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def get_ruleset(self, org_id: str, repo_name: str, ruleset_id: str) -> dict[str, Any]:
        _logger.debug("retrieving ruleset '%s' for repo '%s/%s'", ruleset_id, org_id, repo_name)

        try:
            params = {"includes_parents": "false"}
            return await self.requester.request_json(
                "GET", f"/repos/{org_id}/{repo_name}/rulesets/{ruleset_id}", params=params
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving ruleset for repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def update_ruleset(self, org_id: str, repo_name: str, ruleset_id: int, ruleset: dict[str, Any]) -> None:
        _logger.debug("updating repo ruleset '%d' for repo '%s/%s'", ruleset_id, org_id, repo_name)

        try:
            await self.requester.request_json("PUT", f"/repos/{org_id}/{repo_name}/rulesets/{ruleset_id}", ruleset)
            _logger.debug("updated repo ruleset '%d'", ruleset_id)
        except GitHubException as ex:
            raise RuntimeError(f"failed to update repo ruleset {ruleset_id}:\n{ex}") from ex

    async def add_ruleset(self, org_id: str, repo_name: str, data: dict[str, Any]) -> None:
        name = data["name"]
        _logger.debug("adding repo ruleset with name '%s' for repo '%s/%s'", name, org_id, repo_name)

        try:
            await self.requester.request_json("POST", f"/repos/{org_id}/{repo_name}/rulesets", data)
            _logger.debug("added repo ruleset with name '%s'", name)
        except GitHubException as ex:
            raise RuntimeError(f"failed to add repo ruleset with name '{name}':\n{ex}") from ex

    async def delete_ruleset(self, org_id: str, repo_name: str, ruleset_id: int, name: str) -> None:
        _logger.debug("deleting repo ruleset with name '%s' for repo '%s/%s'", name, org_id, repo_name)

        status, _ = await self.requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}/rulesets/{ruleset_id}")

        if status != 204:
            raise RuntimeError(f"failed to delete repo ruleset with name '{name}'")

        _logger.debug("removed repo ruleset with name '%s'", name)

    @staticmethod
    def _render_template_content(org_id: str, repo_name: str, content: str) -> str:
        variables = {"org": org_id, "repo": repo_name}
        return chevron.render(content, variables)

    async def get_readme(self, org_id: str, repo_name: str) -> dict[str, Any]:
        _logger.debug("getting readme for repo '%s/%s'", org_id, repo_name)

        try:
            return await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/readme")
        except GitHubException as ex:
            raise RuntimeError(f"failed to get readme for repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def delete_repo(self, org_id: str, repo_name: str) -> None:
        _logger.debug("deleting repo '%s/%s'", org_id, repo_name)

        status, body = await self.requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}")

        if status != 204:
            raise RuntimeError(f"failed to delete repo '{org_id}/{repo_name}': {body}")

        _logger.debug("removed repo '%s/%s'", org_id, repo_name)

    @staticmethod
    def _remove_already_active_settings(update_data: dict[str, Any], current_data: dict[str, Any]) -> None:
        keys = list(update_data.keys())
        for key in keys:
            if key in current_data:
                update_value_expected = update_data[key]
                update_value_current = current_data[key]

                if update_value_current == update_value_expected:
                    _logger.debug("omitting setting '%s' as it is already set", key)
                    update_data.pop(key)

    async def _fill_github_pages_config(self, org_id: str, repo_name: str, repo_data: dict[str, Any]) -> None:
        _logger.debug("retrieving github pages config for '%s/%s'", org_id, repo_name)

        status, body = await self.requester.request_raw("GET", f"/repos/{org_id}/{repo_name}/pages")
        if status == 200:
            if is_trace_enabled():
                _logger.trace(
                    "'%s' url = %s, json = %s",
                    "GET",
                    f"/repos/{org_id}/{repo_name}/pages",
                    json.dumps(json.loads(body), indent=2),
                )
            repo_data["gh_pages"] = json.loads(body)

    async def _update_github_pages_config(self, org_id: str, repo_name: str, gh_pages: dict[str, Any]) -> None:
        _logger.debug("updating github pages config for '%s/%s'", org_id, repo_name)

        # special handling for repos hosting the organization site
        if repo_name.lower() == f"{org_id}.github.io".lower():
            current_repo_data: dict[str, Any] = {}
            for i in range(1, 4):
                await self._fill_github_pages_config(org_id, repo_name, current_repo_data)
                if "gh_pages" in current_repo_data:
                    break

                _logger.trace(f"waiting for repo '{org_id}/{repo_name}' to be initialized, try {i} of 3")
                import time

                time.sleep(1)

            current_gh_pages: Any = current_repo_data.get("gh_pages")
            if current_gh_pages is not None:
                has_changes = False
                for k, v in gh_pages.items():
                    if current_gh_pages.get(k, None) != v:
                        has_changes = True
                        break

                # if there are no changes to the current config, we do not need to do anything
                if has_changes is False:
                    _logger.trace(f"github pages config for '{org_id}/{repo_name}' is already up-to-date")
                    return

        build_type = gh_pages.get("build_type")
        if build_type == "disabled":
            status, body = await self.requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}/pages")
            if status != 204 and status != 404:
                raise RuntimeError(f"failed to disable github pages for repo '{repo_name}': {body}")
        else:
            gh_pages_data: list[tuple[str, str, int]] = []
            # first check if the pages config already exists:
            status, _ = await self.requester.request_raw("GET", f"/repos/{org_id}/{repo_name}/pages")
            if status != 200:
                # check if the branch already exists
                source: Any = gh_pages.get("source")
                if source is not None:
                    branch = source.get("branch", None)
                    if branch is not None:
                        existing_branches = await self.get_branches(org_id, repo_name)

                        if len(existing_branches) == 0:
                            _logger.debug("repo '%s' not yet initialized, skipping GH pages config", repo_name)
                            return

                        existing_branch_names = [x["name"] for x in existing_branches]
                        if branch not in existing_branch_names:
                            gh_pages_data.append((json.dumps(gh_pages), "PUT", 204))
                            gh_pages["source"]["branch"] = existing_branch_names[0]
                            gh_pages_data.insert(0, (json.dumps(gh_pages), "POST", 201))

                if len(gh_pages_data) == 0:
                    gh_pages_data.append((json.dumps(gh_pages), "POST", 201))
            else:
                gh_pages_data.append((json.dumps(gh_pages), "PUT", 204))

            for data, method, status_code in gh_pages_data:
                status, body = await self.requester.request_raw(method, f"/repos/{org_id}/{repo_name}/pages", data=data)

                if status != status_code:
                    raise RuntimeError(f"failed to update github pages config for repo '{repo_name}': {body}")

                _logger.debug("updated github pages config for repo '%s'", repo_name)

    async def _fill_code_scanning_config(self, org_id: str, repo_name: str, repo_data: dict[str, Any]) -> None:
        _logger.debug("retrieving code scanning config for '%s/%s'", org_id, repo_name)

        status, body = await self.requester.request_raw(
            "GET", f"/repos/{org_id}/{repo_name}/code-scanning/default-setup"
        )
        if status == 200:
            repo_data["code_scanning_default_config"] = json.loads(body)

    async def _update_code_scanning_config(self, org_id: str, repo_name: str, code_scanning: dict[str, Any]) -> None:
        _logger.debug("updating code scanning config for '%s/%s'", org_id, repo_name)

        try:
            await self.requester.request_json(
                "PATCH", f"/repos/{org_id}/{repo_name}/code-scanning/default-setup", data=code_scanning
            )
            _logger.debug("updated code scanning config for repo '%s/%s'", org_id, repo_name)
        except GitHubException as ex:
            raise RuntimeError(f"failed to update code scanning config for repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def _update_default_branch(self, org_id: str, repo_name: str, new_default_branch: str) -> None:
        _logger.debug("updating default branch for '%s/%s'", org_id, repo_name)
        existing_branches = await self.get_branches(org_id, repo_name)
        existing_branch_names = [x["name"] for x in existing_branches]

        if len(existing_branches) == 0:
            _logger.debug("skip updating of default branch for empty repo '%s/%s'", org_id, repo_name)
            return

        try:
            if new_default_branch in existing_branch_names:
                data = {"default_branch": new_default_branch}
                await self.requester.request_json("PATCH", f"/repos/{org_id}/{repo_name}", data)
                _logger.debug("updated default branch in repo '%s/%s'", org_id, repo_name)
            else:
                default_branch = await self.get_default_branch(org_id, repo_name)
                await self.rename_branch(org_id, repo_name, default_branch, new_default_branch)
                _logger.debug("renamed default branch in repo '%s/%s'", org_id, repo_name)
        except GitHubException as ex:
            raise RuntimeError(f"failed to update default branch for repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def _fill_vulnerability_alerts(self, org_id: str, repo_name: str, repo_data: dict[str, Any]) -> None:
        _logger.debug("retrieving repo vulnerability alerts for '%s/%s'", org_id, repo_name)

        status, _ = await self.requester.request_raw("GET", f"/repos/{org_id}/{repo_name}/vulnerability-alerts")
        if status == 204:
            repo_data["dependabot_alerts_enabled"] = True
        else:
            repo_data["dependabot_alerts_enabled"] = False

    async def _update_vulnerability_alerts(self, org_id: str, repo_name: str, vulnerability_reports: bool) -> None:
        _logger.debug("updating repo vulnerability alerts for '%s/%s'", org_id, repo_name)

        method = "PUT" if vulnerability_reports is True else "DELETE"

        status, body = await self.requester.request_raw(method, f"/repos/{org_id}/{repo_name}/vulnerability-alerts")

        if status != 204:
            raise RuntimeError(f"failed to update vulnerability alerts for repo '{org_id}/{repo_name}': {body}")

        _logger.debug("updated vulnerability alerts for repo '%s/%s'", org_id, repo_name)

    async def _fill_private_vulnerability_reporting(
        self, org_id: str, repo_name: str, repo_data: dict[str, Any]
    ) -> None:
        _logger.debug("retrieving repo private vulnerability reporting status for '%s/%s'", org_id, repo_name)

        response = await self.requester.request_json(
            "GET", f"/repos/{org_id}/{repo_name}/private-vulnerability-reporting"
        )
        repo_data["private_vulnerability_reporting_enabled"] = response["enabled"]

    async def _update_private_vulnerability_reporting(
        self, org_id: str, repo_name: str, private_vulnerability_reporting_enabled: bool
    ) -> None:
        _logger.debug("updating repo private vulnerability reporting for '%s/%s'", org_id, repo_name)

        method = "PUT" if private_vulnerability_reporting_enabled is True else "DELETE"

        status, body = await self.requester.request_raw(
            method, f"/repos/{org_id}/{repo_name}/private-vulnerability-reporting"
        )

        if status != 204:
            raise RuntimeError(
                f"failed to update private vulnerability reporting for repo '{org_id}/{repo_name}': {body}"
            )

        _logger.debug("updated private vulnerability reporting for repo '%s/%s'", org_id, repo_name)

    async def _fill_topics(self, org_id: str, repo_name: str, repo_data: dict[str, Any]) -> None:
        _logger.debug("retrieving repo topics for '%s/%s'", org_id, repo_name)

        try:
            response = await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/topics")
            repo_data["topics"] = response.get("names", [])
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving topics for repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def _update_topics(self, org_id: str, repo_name: str, topics: list[str]) -> None:
        _logger.debug("updating repo topics for '%s/%s'", org_id, repo_name)
        data = {"names": topics}
        await self.requester.request_json("PUT", f"/repos/{org_id}/{repo_name}/topics", data=data)
        _logger.debug("updated topics for repo '%s'", repo_name)

    async def _fill_custom_properties(self, org_id: str, repo_name: str, repo_data: dict[str, Any]) -> None:
        _logger.debug("retrieving repo custom properties for '%s/%s'", org_id, repo_name)

        try:
            response = await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/properties/values")
            repo_data["custom_properties"] = response
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving custom properties for repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def _update_custom_properties(
        self, org_id: str, repo_name: str, custom_properties: list[dict[str, str | list[str]]]
    ) -> None:
        _logger.debug("updating repo custom properties for '%s/%s'", org_id, repo_name)
        data = {"properties": custom_properties}
        status, body = await self.requester.request_raw(
            "PATCH", f"/repos/{org_id}/{repo_name}/properties/values", data=json.dumps(data)
        )

        if status != 204:
            raise RuntimeError(f"failed to update custom properties for repo '{org_id}/{repo_name}': {body}")

        _logger.debug("updated custom properties for repo '%s'", repo_name)

    async def get_branches(self, org_id: str, repo_name) -> list[dict[str, Any]]:
        _logger.debug("retrieving branches for repo '%s/%s'", org_id, repo_name)

        try:
            return await self.requester.request_paged_json("GET", f"/repos/{org_id}/{repo_name}/branches")
        except GitHubException as ex:
            raise RuntimeError(f"failed getting branches for repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def get_tags(self, org_id: str, repo_name: str) -> list[dict[str, Any]] | None:
        _logger.debug("retrieving tags for repo '%s/%s'", org_id, repo_name)

        try:
            return await self.requester.request_paged_json("GET", f"/repos/{org_id}/{repo_name}/tags")
        except GitHubException as ex:
            raise RuntimeError(f"failed getting tags for repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def get_environments(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving environments for repo '%s/%s'", org_id, repo_name)

        try:
            response = await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/environments")

            environments = response["environments"]
            for env in environments:
                env_name = env["name"]
                has_branch_policies = bool(query_json("deployment_branch_policy.custom_branch_policies", env) or False)

                if has_branch_policies:
                    env["branch_policies"] = await self._get_deployment_branch_policies(org_id, repo_name, env_name)
            return environments
        except GitHubException:
            # querying the environments might fail for private repos, ignore exceptions
            return []

    async def update_environment(self, org_id: str, repo_name: str, env_name: str, env: dict[str, Any]) -> None:
        _logger.debug("updating environment '%s' for repo '%s/%s'", env_name, org_id, repo_name)

        if "name" in env:
            env.pop("name")

        branch_policies = env.pop("branch_policies") if "branch_policies" in env else None

        try:
            await self.requester.request_json("PUT", f"/repos/{org_id}/{repo_name}/environments/{env_name}", env)

            if branch_policies is not None:
                await self._update_deployment_branch_policies(org_id, repo_name, env_name, branch_policies)

            _logger.debug("updated repo environment '%s'", env_name)
        except GitHubException as ex:
            raise RuntimeError(f"failed to update repo environment '{env_name}':\n{ex}") from ex

    async def add_environment(self, org_id: str, repo_name: str, env_name: str, data: dict[str, Any]) -> None:
        _logger.debug("adding environment '%s' for repo '%s/%s'", env_name, org_id, repo_name)
        await self.update_environment(org_id, repo_name, env_name, data)
        _logger.debug("added environment '%s'", env_name)

    async def delete_environment(self, org_id: str, repo_name: str, env_name: str) -> None:
        _logger.debug("deleting repo environment '%s' for repo '%s/%s'", env_name, org_id, repo_name)

        status, _ = await self.requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}/environments/{env_name}")

        if status != 204:
            raise RuntimeError(f"failed to delete repo environment '{env_name}'")

        _logger.debug("removed repo environment '%s'", env_name)

    async def _get_deployment_branch_policies(self, org_id: str, repo_name: str, env_name: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving deployment branch policies for env '%s'", env_name)

        try:
            url = f"/repos/{org_id}/{repo_name}/environments/{env_name}/deployment-branch-policies"
            response = await self.requester.request_json("GET", url)
            return response["branch_policies"]
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving deployment branch policies:\n{ex}") from ex

    async def _update_deployment_branch_policies(
        self, org_id: str, repo_name: str, env_name: str, branch_policies: list[str]
    ) -> None:
        _logger.debug("updating deployment branch policies for env '%s'", env_name)

        try:
            current_branch_policies_by_name = associate_by_key(
                await self._get_deployment_branch_policies(org_id, repo_name, env_name),
                lambda x: f"{x.get('type', 'branch')}:{x['name']}",
            )
        except RuntimeError:
            current_branch_policies_by_name = {}

        try:

            def transform_policies(x: str):
                if x.startswith("tag:"):
                    return f"tag:{x[4:]}"
                else:
                    return f"branch:{x}"

            for policy in map(transform_policies, branch_policies):
                if policy in current_branch_policies_by_name:
                    current_branch_policies_by_name.pop(policy)
                else:
                    await self._create_deployment_branch_policy(org_id, repo_name, env_name, policy)

            for _policy_name, policy_dict in current_branch_policies_by_name.items():
                await self._delete_deployment_branch_policy(org_id, repo_name, env_name, policy_dict["id"])

            _logger.debug("updated deployment branch policies for env '%s'", env_name)

        except GitHubException as ex:
            raise RuntimeError(f"failed creating deployment branch policies:\n{ex}") from ex

    async def _create_deployment_branch_policy(
        self, org_id: str, repo_name: str, env_name: str, name_and_type: str
    ) -> None:
        _logger.debug("creating deployment branch policy for env '%s' with type/name '%s", env_name, name_and_type)

        try:
            target_type, name = name_and_type.split(":", 1)
            data = {"name": name, "type": target_type}
            url = f"/repos/{org_id}/{repo_name}/environments/{env_name}/deployment-branch-policies"
            await self.requester.request_json("POST", url, data)
            _logger.debug("created deployment branch policy for env '%s'", env_name)
        except GitHubException as ex:
            raise RuntimeError(f"failed creating deployment branch policy:\n{ex}") from ex

    async def _delete_deployment_branch_policy(
        self, org_id: str, repo_name: str, env_name: str, policy_id: int
    ) -> None:
        _logger.debug("deleting deployment branch policy for env '%s' with id '%d", env_name, policy_id)

        url = f"/repos/{org_id}/{repo_name}/environments/{env_name}/deployment-branch-policies/{policy_id}"
        status, body = await self.requester.request_raw("DELETE", url)

        if status != 204:
            raise RuntimeError(f"failed deleting deployment branch policy\n{status}: {body}")

        _logger.debug("deleted deployment branch policy for env '%s'", env_name)

    async def get_secrets(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving secrets for repo '%s/%s'", org_id, repo_name)

        try:
            status, body = await self.requester.request_raw("GET", f"/repos/{org_id}/{repo_name}/actions/secrets")
            if status == 200:
                return json.loads(body)["secrets"]
            else:
                return []
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving secrets for repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def update_secret(self, org_id: str, repo_name: str, secret_name: str, secret: dict[str, Any]) -> None:
        _logger.debug("updating repo secret '%s' for repo '%s/%s'", secret_name, org_id, repo_name)

        if "name" in secret:
            secret.pop("name")

        await self._encrypt_secret_inplace(org_id, repo_name, secret)

        status, _ = await self.requester.request_raw(
            "PUT",
            f"/repos/{org_id}/{repo_name}/actions/secrets/{secret_name}",
            json.dumps(secret),
        )

        if status != 204:
            raise RuntimeError(f"failed to update repo secret '{secret_name}'")

        _logger.debug("updated repo secret '%s'", secret_name)

    async def add_secret(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        secret_name = data.pop("name")
        _logger.debug("adding repo secret '%s' for repo '%s/%s'", secret_name, org_id, repo_name)

        await self._encrypt_secret_inplace(org_id, repo_name, data)

        status, _ = await self.requester.request_raw(
            "PUT",
            f"/repos/{org_id}/{repo_name}/actions/secrets/{secret_name}",
            json.dumps(data),
        )

        if status != 201:
            raise RuntimeError(f"failed to add repo secret '{secret_name}'")

        _logger.debug("added repo secret '%s'", secret_name)

    async def _encrypt_secret_inplace(self, org_id: str, repo_name: str, data: dict[str, Any]) -> None:
        value = data.pop("value")
        key_id, public_key = await self.get_public_key(org_id, repo_name)
        data["encrypted_value"] = encrypt_value(public_key, value)
        data["key_id"] = key_id

    async def delete_secret(self, org_id: str, repo_name: str, secret_name: str) -> None:
        _logger.debug("deleting repo secret '%s' for repo '%s/%s'", secret_name, org_id, repo_name)

        status, _ = await self.requester.request_raw(
            "DELETE", f"/repos/{org_id}/{repo_name}/actions/secrets/{secret_name}"
        )

        if status != 204:
            raise RuntimeError(f"failed to delete repo secret '{secret_name}'")

        _logger.debug("removed repo secret '%s'", secret_name)

    async def get_variables(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving variables for repo '%s/%s'", org_id, repo_name)

        try:
            status, body = await self.requester.request_raw("GET", f"/repos/{org_id}/{repo_name}/actions/variables")
            if status == 200:
                return json.loads(body)["variables"]
            else:
                return []
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving variables for repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def update_variable(self, org_id: str, repo_name: str, variable_name: str, variable: dict[str, Any]) -> None:
        _logger.debug("updating repo variable '%s' for repo '%s/%s'", variable_name, org_id, repo_name)

        if "name" in variable:
            variable.pop("name")

        status, body = await self.requester.request_raw(
            "PATCH",
            f"/repos/{org_id}/{repo_name}/actions/variables/{variable_name}",
            json.dumps(variable),
        )
        if status != 204:
            raise RuntimeError(f"failed to update repo variable '{variable_name}': {body}")

        _logger.debug("updated repo variable '%s'", variable_name)

    async def add_variable(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        variable_name = data.get("name")
        _logger.debug("adding repo variable '%s' for repo '%s/%s'", variable_name, org_id, repo_name)

        status, body = await self.requester.request_raw(
            "POST",
            f"/repos/{org_id}/{repo_name}/actions/variables",
            json.dumps(data),
        )

        if status != 201:
            raise RuntimeError(f"failed to add repo variable '{variable_name}': {body}")

        _logger.debug("added repo variable '%s'", variable_name)

    async def delete_variable(self, org_id: str, repo_name: str, variable_name: str) -> None:
        _logger.debug("deleting repo variable '%s' for repo '%s/%s'", variable_name, org_id, repo_name)

        status, _ = await self.requester.request_raw(
            "DELETE", f"/repos/{org_id}/{repo_name}/actions/variables/{variable_name}"
        )

        if status != 204:
            raise RuntimeError(f"failed to delete repo variable '{variable_name}'")

        _logger.debug("removed repo variable '%s'", variable_name)

    async def get_workflow_settings(self, org_id: str, repo_name: str) -> dict[str, Any]:
        _logger.debug("retrieving workflow settings for repo '%s/%s'", org_id, repo_name)

        workflow_settings: dict[str, Any] = {}

        try:
            permissions = await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/actions/permissions")
            workflow_settings.update(permissions)
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving workflow settings for repo '{org_id}/{repo_name}':\n{ex}") from ex

        allowed_actions = permissions.get("allowed_actions", "none")
        if allowed_actions == "selected":
            workflow_settings.update(await self._get_selected_actions_for_workflow_settings(org_id, repo_name))

        if permissions.get("enabled", False) is not False:
            workflow_settings.update(await self._get_default_workflow_permissions(org_id, repo_name))

        return workflow_settings

    async def update_workflow_settings(self, org_id: str, repo_name: str, data: dict[str, Any]) -> None:
        _logger.debug("updating workflow settings for repo '%s/%s'", org_id, repo_name)

        permission_data = {k: data[k] for k in ["enabled", "allowed_actions"] if k in data}
        if len(permission_data) > 0:
            status, body = await self.requester.request_raw(
                "PUT", f"/repos/{org_id}/{repo_name}/actions/permissions", json.dumps(permission_data)
            )

            if status != 204:
                raise RuntimeError(
                    f"failed to update workflow settings for repo '{org_id}/{repo_name}'\n{status}: {body}"
                )

            _logger.debug("updated workflow settings for repo '%s/%s'", org_id, repo_name)

        # only update the selected actions if needed
        if data.get("allowed_actions", "selected") == "selected":
            allowed_action_data = {
                k: data[k] for k in ["github_owned_allowed", "verified_allowed", "patterns_allowed"] if k in data
            }
            if len(allowed_action_data) > 0:
                await self._update_selected_actions_for_workflow_settings(org_id, repo_name, allowed_action_data)

        default_permission_data = {
            k: data[k] for k in ["default_workflow_permissions", "can_approve_pull_request_reviews"] if k in data
        }
        if len(default_permission_data) > 0:
            await self._update_default_workflow_permissions(org_id, repo_name, default_permission_data)

        _logger.debug("updated %d workflow setting(s)", len(data))

    async def _get_selected_actions_for_workflow_settings(self, org_id: str, repo_name: str) -> dict[str, Any]:
        _logger.debug("retrieving allowed actions for repo '%s/%s'", org_id, repo_name)

        try:
            return await self.requester.request_json(
                "GET", f"/repos/{org_id}/{repo_name}/actions/permissions/selected-actions"
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving allowed actions for repo '{org_id}/{repo_name}':\n{ex}") from ex

    async def _update_selected_actions_for_workflow_settings(
        self, org_id: str, repo_name: str, data: dict[str, Any]
    ) -> None:
        _logger.debug("updating allowed actions for repo '%s/%s'", org_id, repo_name)

        status, body = await self.requester.request_raw(
            "PUT", f"/repos/{org_id}/{repo_name}/actions/permissions/selected-actions", json.dumps(data)
        )

        if status != 204:
            raise RuntimeError(f"failed updating allowed actions for repo '{org_id}/{repo_name}'\n{status}: {body}")

        _logger.debug("updated allowed actions for repo '%s/%s'", org_id, repo_name)

    async def _get_default_workflow_permissions(self, org_id: str, repo_name: str) -> dict[str, Any]:
        _logger.debug("retrieving default workflow permissions for repo '%s/%s'", org_id, repo_name)

        try:
            return await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/actions/permissions/workflow")
        except GitHubException as ex:
            raise RuntimeError(
                f"failed retrieving default workflow permissions for repo '{org_id}/{repo_name}':\n{ex}"
            ) from ex

    async def _update_default_workflow_permissions(self, org_id: str, repo_name: str, data: dict[str, Any]) -> None:
        _logger.debug("updating default workflow permissions for repo '%s/%s'", org_id, repo_name)

        status, body = await self.requester.request_raw(
            "PUT", f"/repos/{org_id}/{repo_name}/actions/permissions/workflow", json.dumps(data)
        )

        if status != 204:
            raise RuntimeError(
                f"failed updating default workflow permissions for repo '{org_id}/{repo_name}'\n{status}: {body}"
            )

        _logger.debug("updated default workflow permissions for repo '%s/%s'", org_id, repo_name)

    async def get_public_key(self, org_id: str, repo_name: str) -> tuple[str, str]:
        _logger.debug("retrieving repo public key for repo '%s/%s'", org_id, repo_name)

        try:
            response = await self.requester.request_json(
                "GET", f"/repos/{org_id}/{repo_name}/actions/secrets/public-key"
            )
            return response["key_id"], response["key"]
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving repo public key:\n{ex}") from ex

    async def dispatch_workflow(self, org_id: str, repo_name: str, workflow_name: str) -> bool:
        _logger.debug("dispatching workflow for repo '%s/%s'", org_id, repo_name)

        default_branch = await self.get_default_branch(org_id, repo_name)
        data = {"ref": default_branch}

        status, _ = await self.requester.request_raw(
            "POST", f"/repos/{org_id}/{repo_name}/actions/workflows/{workflow_name}/dispatches", json.dumps(data)
        )

        if status != 204:
            _logger.debug("failed dispatching workflow for repo '%s/%s'", org_id, repo_name)
            return False
        else:
            _logger.debug("dispatched workflow for repo '%s/%s'", org_id, repo_name)
            return True

    async def get_ref_for_pull_request(self, org_id: str, repo_name: str, pull_number: str) -> str:
        _logger.debug(f"retrieving ref for pull request {pull_number} at {org_id}/{repo_name}")

        try:
            response = await self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/pulls/{pull_number}")
            return response["head"]["sha"]
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving ref for pull request:\n{ex}") from ex

    async def sync_from_template_repository(
        self,
        org_id: str,
        repo_name: str,
        template_repository: str,
        template_paths: list[str] | None,
    ) -> list[str]:
        template_owner, template_repo = re.split("/", template_repository, maxsplit=1)

        updated_files = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            archive_file_name = os.path.join(tmp_dir, "archive.zip")
            async with aiofiles.open(archive_file_name, "wb") as archive_file:
                await self._download_repository_archive(archive_file, template_owner, template_repo)

            archive_target_dir = os.path.join(tmp_dir, "contents")
            with zipfile.ZipFile(archive_file_name, "r") as zip_file:
                zip_file.extractall(archive_target_dir)

            template_paths_set = set(template_paths) if isinstance(template_paths, list) else set()

            base_dir = None
            for path in pathlib.Path(archive_target_dir).rglob("*"):
                # the downloaded archive starts with a subdir that encodes
                # the name / hash of the downloaded repo, use that as the base dir
                # to resolve relative path names for updating the content.
                if base_dir is None:
                    base_dir = path

                relative_path = path.relative_to(base_dir)

                if path.is_file():
                    _logger.debug("updating file '%s'", relative_path)

                    with open(path) as file:
                        content = file.read()

                        if str(relative_path) in template_paths_set:
                            content = self._render_template_content(org_id, repo_name, content)

                        updated = await self.rest_api.content.update_content(
                            org_id, repo_name, str(relative_path), content
                        )
                        if updated:
                            updated_files.append(str(relative_path))

        return updated_files

    async def _download_repository_archive(self, file, org_id: str, repo_name: str, ref: str = "") -> None:
        _logger.debug("downloading repository archive for '%s/%s'", org_id, repo_name)

        try:
            async for data in self.requester.request_stream("GET", f"/repos/{org_id}/{repo_name}/zipball/{ref}"):
                await file.write(data)

        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving repository archive from repo '{org_id}/{repo_name}':\n{ex}") from ex
