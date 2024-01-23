#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************


import json
import os
import pathlib
import re
import tempfile
import zipfile
from typing import IO, Any, Optional

import chevron
import jq  # type: ignore

from otterdog.providers.github.exception import GitHubException
from otterdog.providers.github.rest import RestApi, RestClient, encrypt_value
from otterdog.utils import (
    associate_by_key,
    is_set_and_present,
    print_debug,
    print_trace,
)


class RepoClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    def get_repo_data(self, org_id: str, repo_name: str) -> dict[str, Any]:
        print_debug(f"retrieving org repo data for '{org_id}/{repo_name}'")

        try:
            repo_data = self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}")
            self._fill_github_pages_config(org_id, repo_name, repo_data)
            self._fill_vulnerability_report(org_id, repo_name, repo_data)
            self._fill_topics(org_id, repo_name, repo_data)
            return repo_data
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving data for repo '{repo_name}':\n{ex}").with_traceback(tb)

    async def async_get_repo_data(self, org_id: str, repo_name: str) -> dict[str, Any]:
        print_debug(f"async retrieving org repo data for '{org_id}/{repo_name}'")

        try:
            repo_data = await self.requester.async_request_json("GET", f"/repos/{org_id}/{repo_name}")
            await self._async_fill_github_pages_config(org_id, repo_name, repo_data)
            await self._async_fill_vulnerability_report(org_id, repo_name, repo_data)
            await self._async_fill_topics(org_id, repo_name, repo_data)
            return repo_data
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving data for repo '{repo_name}':\n{ex}").with_traceback(tb)

    def get_repo_by_id(self, repo_id: int) -> dict[str, Any]:
        print_debug(f"retrieving repo by id for '{repo_id}'")

        try:
            return self.requester.request_json("GET", f"/repositories/{repo_id}")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving data for repo '{repo_id}':\n{ex}").with_traceback(tb)

    def update_repo(self, org_id: str, repo_name: str, data: dict[str, Any]) -> None:
        print_debug(f"updating repo settings for repo '{org_id}/{repo_name}'")

        changes = len(data)

        if "dependabot_alerts_enabled" in data:
            vulnerability_reports = bool(data.pop("dependabot_alerts_enabled"))
        else:
            vulnerability_reports = None

        if "topics" in data:
            topics = list(data.pop("topics"))
        else:
            topics = None

        if "gh_pages" in data:
            gh_pages = data.pop("gh_pages")
        else:
            gh_pages = None

        if "default_branch" in data:
            default_branch = data.pop("default_branch")
        else:
            default_branch = None

        if changes > 0:
            try:
                if len(data) > 0:
                    self.requester.request_json("PATCH", f"/repos/{org_id}/{repo_name}", data)

                if vulnerability_reports is not None:
                    self._update_vulnerability_report(org_id, repo_name, vulnerability_reports)
                if topics is not None:
                    self._update_topics(org_id, repo_name, topics)
                if gh_pages is not None:
                    self._update_github_pages_config(org_id, repo_name, gh_pages)
                if default_branch is not None:
                    self._update_default_branch(org_id, repo_name, default_branch)

                print_debug(f"updated {changes} repo setting(s) for repo '{repo_name}'")
            except GitHubException as ex:
                tb = ex.__traceback__
                raise RuntimeError(f"failed to update settings for repo '{repo_name}':\n{ex}").with_traceback(tb)

    def add_repo(
        self,
        org_id: str,
        data: dict[str, Any],
        template_repository: Optional[str],
        post_process_template_content: list[str],
        forked_repository: Optional[str],
        fork_default_branch_only: bool,
        auto_init_repo: bool,
    ) -> None:
        repo_name = data["name"]

        if is_set_and_present(forked_repository):
            print_debug(f"forking repo '{forked_repository}' to '{org_id}/{repo_name}'")
            upstream_owner, upstream_repo = re.split("/", forked_repository, 1)

            try:
                fork_data = {
                    "organization": org_id,
                    "name": repo_name,
                    "default_branch_only": fork_default_branch_only,
                }

                self.requester.request_json(
                    "POST",
                    f"/repos/{upstream_owner}/{upstream_repo}/forks",
                    fork_data,
                )

                print_debug(f"created repo with name '{repo_name}' from template '{template_repository}'")

                # get all the data for the created repo to avoid setting values that can not be changed due
                # to defaults from the organization (like web_commit_signoff_required)
                current_data = self.get_repo_data(org_id, repo_name)
                self._remove_already_active_settings(data, current_data)
                self.update_repo(org_id, repo_name, data)

                return
            except GitHubException as ex:
                tb = ex.__traceback__
                raise RuntimeError(
                    f"failed to fork repo '{repo_name}' from repo '{forked_repository}':\n{ex}"
                ).with_traceback(tb)

        if is_set_and_present(template_repository):
            print_debug(f"creating repo '{org_id}/{repo_name}' with template '{template_repository}'")
            template_owner, template_repo = re.split("/", template_repository, 1)

            try:
                template_data = {
                    "owner": org_id,
                    "name": repo_name,
                    "include_all_branches": False,
                    "private": data.get("private", False),
                }

                self.requester.request_json(
                    "POST",
                    f"/repos/{template_owner}/{template_repo}/generate",
                    template_data,
                )

                print_debug(f"created repo with name '{repo_name}' from template '{template_repository}'")

                # get all the data for the created repo to avoid setting values that can not be changed due
                # to defaults from the organization (like web_commit_signoff_required)
                current_data = self.get_repo_data(org_id, repo_name)
                self._remove_already_active_settings(data, current_data)
                self.update_repo(org_id, repo_name, data)

                # wait till the repo is initialized, this might take a while.
                if len(post_process_template_content) > 0:
                    initialized = False
                    for i in range(1, 11):
                        try:
                            self.get_readme(org_id, repo_name)
                            initialized = True
                            break
                        except RuntimeError:
                            print_trace(f"waiting for repo '{org_id}/{repo_name}' to be initialized, " f"try {i} of 10")
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
                    content = self.rest_api.content.get_content(org_id, repo_name, content_path, None)
                    updated_content = self._render_template_content(org_id, repo_name, content)
                    if content != updated_content:
                        self.rest_api.content.update_content(org_id, repo_name, content_path, updated_content)

                return
            except GitHubException as ex:
                tb = ex.__traceback__
                raise RuntimeError(
                    f"failed to create repo from template '{template_repository}':\n{ex}"
                ).with_traceback(tb)

        print_debug(f"creating repo '{org_id}/{repo_name}'")

        # some settings do not seem to be set correctly during creation
        # collect them and update the repo after creation.
        update_keys = [
            "dependabot_alerts_enabled",
            "web_commit_signoff_required",
            "security_and_analysis",
            "topics",
            "gh_pages",
        ]

        if auto_init_repo is True:
            update_keys.append("default_branch")

        update_data = {}

        for update_key in update_keys:
            if update_key in data:
                update_data[update_key] = data.pop(update_key)

        # whether the repo should be initialized with an empty README
        data["auto_init"] = auto_init_repo

        try:
            result = self.requester.request_json("POST", f"/orgs/{org_id}/repos", data)
            print_debug(f"created repo with name '{repo_name}'")
            self._remove_already_active_settings(update_data, result)
            self.update_repo(org_id, repo_name, update_data)
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to add repo with name '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)

    def get_webhooks(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving webhooks for repo '{org_id}/{repo_name}'")

        try:
            # special handling due to temporary private forks for security advisories.
            #  example repo: https://github.com/eclipse-cbi/jiro-ghsa-wqjm-x66q-r2c6
            # currently it is not possible via the api to determine such repos, but when
            # requesting hooks for such a repo, you would get a 404 response.
            response = self.requester.request_raw("GET", f"/repos/{org_id}/{repo_name}/hooks")
            if response.status_code == 200:
                return response.json()
            else:
                return []
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving webhooks for repo '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)

    async def async_get_webhooks(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        print_debug(f"async retrieving webhooks for repo '{org_id}/{repo_name}'")

        try:
            # special handling due to temporary private forks for security advisories.
            #  example repo: https://github.com/eclipse-cbi/jiro-ghsa-wqjm-x66q-r2c6
            # currently it is not possible via the api to determine such repos, but when
            # requesting hooks for such a repo, you would get a 404 response.
            status, body = await self.requester.async_request_raw("GET", f"/repos/{org_id}/{repo_name}/hooks")
            if status == 200:
                return json.loads(body)
            else:
                return []
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving webhooks for repo '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)

    def update_webhook(self, org_id: str, repo_name: str, webhook_id: int, webhook: dict[str, Any]) -> None:
        print_debug(f"updating repo webhook '{webhook_id}' for repo '{org_id}/{repo_name}'")

        try:
            self.requester.request_json("PATCH", f"/repos/{org_id}/{repo_name}/hooks/{webhook_id}", webhook)
            print_debug(f"updated repo webhook '{webhook_id}'")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to update repo webhook {webhook_id}:\n{ex}").with_traceback(tb)

    def add_webhook(self, org_id: str, repo_name: str, data: dict[str, Any]) -> None:
        url = data["config"]["url"]
        print_debug(f"adding repo webhook with url '{url}' for repo '{org_id}/{repo_name}'")

        # mandatory field "name" = "web"
        data["name"] = "web"

        try:
            self.requester.request_json("POST", f"/repos/{org_id}/{repo_name}/hooks", data)
            print_debug(f"added repo webhook with url '{url}'")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to add repo webhook with url '{url}':\n{ex}").with_traceback(tb)

    def delete_webhook(self, org_id: str, repo_name: str, webhook_id: int, url: str) -> None:
        print_debug(f"deleting repo webhook with url '{url}' for repo '{org_id}/{repo_name}'")

        response = self.requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}/hooks/{webhook_id}")

        if response.status_code != 204:
            raise RuntimeError(f"failed to delete repo webhook with url '{url}'")

        print_debug(f"removed repo webhook with url '{url}'")

    async def async_get_rulesets(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        print_debug(f"async retrieving rulesets for repo '{org_id}/{repo_name}'")

        try:
            result = []
            params = {"includes_parents": str(False)}
            response = await self.requester.async_request_paged_json(
                "GET", f"/repos/{org_id}/{repo_name}/rulesets", params=params
            )
            for ruleset in response:
                result.append(await self.async_get_ruleset(org_id, repo_name, str(ruleset["id"])))
            return result
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving rulesets for repo '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)

    async def async_get_ruleset(self, org_id: str, repo_name: str, ruleset_id: str) -> dict[str, Any]:
        print_debug(f"async retrieving ruleset '{ruleset_id}' for repo '{org_id}/{repo_name}'")

        try:
            params = {"includes_parents": str(False)}
            return await self.requester.async_request_json(
                "GET", f"/repos/{org_id}/{repo_name}/rulesets/{ruleset_id}", params=params
            )
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving ruleset for repo '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)

    def update_ruleset(self, org_id: str, repo_name: str, ruleset_id: int, ruleset: dict[str, Any]) -> None:
        print_debug(f"updating repo ruleset '{ruleset_id}' for repo '{org_id}/{repo_name}'")

        try:
            self.requester.request_json("PUT", f"/repos/{org_id}/{repo_name}/rulesets/{ruleset_id}", ruleset)
            print_debug(f"updated repo ruleset '{ruleset_id}'")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to update repo ruleset {ruleset_id}:\n{ex}").with_traceback(tb)

    def add_ruleset(self, org_id: str, repo_name: str, data: dict[str, Any]) -> None:
        name = data["name"]
        print_debug(f"adding repo ruleset with name '{name}' for repo '{org_id}/{repo_name}'")

        # TODO: currently we only support rulesets targetting branches
        data["target"] = "branch"

        try:
            self.requester.request_json("POST", f"/repos/{org_id}/{repo_name}/rulesets", data)
            print_debug(f"added repo ruleset with name '{name}'")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to add repo ruleset with name '{name}':\n{ex}").with_traceback(tb)

    def delete_ruleset(self, org_id: str, repo_name: str, ruleset_id: int, name: str) -> None:
        print_debug(f"deleting repo ruleset with name '{name}' for repo '{org_id}/{repo_name}'")

        response = self.requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}/rulesets/{ruleset_id}")

        if response.status_code != 204:
            raise RuntimeError(f"failed to delete repo ruleset with name '{name}'")

        print_debug(f"removed repo ruleset with name '{name}'")

    @staticmethod
    def _render_template_content(org_id: str, repo_name: str, content: str) -> str:
        variables = {"org": org_id, "repo": repo_name}

        return chevron.render(content, variables)

    def get_readme(self, org_id: str, repo_name: str) -> dict[str, Any]:
        print_debug(f"getting readme for repo '{org_id}/{repo_name}'")

        try:
            return self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/readme")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to get readme for repo '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)

    def delete_repo(self, org_id: str, repo_name: str) -> None:
        print_debug(f"deleting repo '{org_id}/{repo_name}'")

        response = self.requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}")

        if response.status_code != 204:
            raise RuntimeError(f"failed to delete repo '{org_id}/{repo_name}': {response.text}")

        print_debug(f"removed repo '{org_id}/{repo_name}'")

    @staticmethod
    def _remove_already_active_settings(update_data: dict[str, Any], current_data: dict[str, Any]) -> None:
        keys = list(update_data.keys())
        for key in keys:
            if key in current_data:
                update_value_expected = update_data[key]
                update_value_current = current_data[key]

                if update_value_current == update_value_expected:
                    print_debug(f"omitting setting '{key}' as it is already set")
                    update_data.pop(key)

    def _fill_github_pages_config(self, org_id: str, repo_name: str, repo_data: dict[str, Any]) -> None:
        print_debug(f"retrieving github pages config for '{org_id}/{repo_name}'")

        response = self.requester.request_raw("GET", f"/repos/{org_id}/{repo_name}/pages")
        if response.status_code == 200:
            repo_data["gh_pages"] = response.json()

    async def _async_fill_github_pages_config(self, org_id: str, repo_name: str, repo_data: dict[str, Any]) -> None:
        print_debug(f"async retrieving github pages config for '{org_id}/{repo_name}'")

        status, body = await self.requester.async_request_raw("GET", f"/repos/{org_id}/{repo_name}/pages")
        if status == 200:
            repo_data["gh_pages"] = json.loads(body)

    def _update_github_pages_config(self, org_id: str, repo_name: str, gh_pages: dict[str, Any]) -> None:
        print_debug(f"updating github pages config for '{org_id}/{repo_name}'")

        # special handling for repos hosting the organization site
        if repo_name.lower() == f"{org_id}.github.io".lower():
            current_repo_data: dict[str, Any] = {}
            for i in range(1, 4):
                self._fill_github_pages_config(org_id, repo_name, current_repo_data)
                if "gh_pages" in current_repo_data:
                    break

                print_trace(f"waiting for repo '{org_id}/{repo_name}' to be initialized, " f"try {i} of 3")
                import time

                time.sleep(1)

            current_gh_pages = current_repo_data.get("gh_pages", None)
            if current_gh_pages is not None:
                has_changes = False
                for k, v in gh_pages.items():
                    if current_gh_pages.get(k, None) != v:
                        has_changes = True
                        break

                # if there are no changes to the current config, we do not need to do anything
                if has_changes is False:
                    print_trace(f"github pages config for '{org_id}/{repo_name}' is already up-to-date")
                    return

        build_type = gh_pages.get("build_type", None)
        if build_type == "disabled":
            self.requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}/pages")
        else:
            gh_pages_data: list[tuple[str, str, int]] = []
            # first check if the pages config already exists:
            response_get = self.requester.request_raw("GET", f"/repos/{org_id}/{repo_name}/pages")
            if response_get.status_code != 200:
                # check if the branch already exists
                source = gh_pages.get("source", None)
                if source is not None:
                    branch = source.get("branch", None)
                    if branch is not None:
                        existing_branches = self.get_branches(org_id, repo_name)

                        if len(existing_branches) == 0:
                            print_debug(f"repo '{repo_name}' not yet initialized, skipping GH pages config")
                            return

                        existing_branch_names = list(map(lambda x: x["name"], existing_branches))
                        if branch not in existing_branch_names:
                            gh_pages_data.append((json.dumps(gh_pages), "PUT", 204))
                            gh_pages["source"]["branch"] = existing_branch_names[0]
                            gh_pages_data.insert(0, (json.dumps(gh_pages), "POST", 201))

                if len(gh_pages_data) == 0:
                    gh_pages_data.append((json.dumps(gh_pages), "POST", 201))
            else:
                gh_pages_data.append((json.dumps(gh_pages), "PUT", 204))

            for data, method, status_code in gh_pages_data:
                response = self.requester.request_raw(method, f"/repos/{org_id}/{repo_name}/pages", data=data)
                if response.status_code != status_code:
                    raise RuntimeError(f"failed to update github pages config for repo '{repo_name}': {response.text}")
                else:
                    print_debug(f"updated github pages config for repo '{repo_name}'")

    def _update_default_branch(self, org_id: str, repo_name: str, new_default_branch: str) -> None:
        print_debug(f"updating default branch for '{org_id}/{repo_name}'")
        existing_branches = self.get_branches(org_id, repo_name)
        existing_branch_names = list(map(lambda x: x["name"], existing_branches))

        if len(existing_branches) == 0:
            print_debug(f"skip updating of default branch for empty repo '{org_id}/{repo_name}'")
            return

        try:
            if new_default_branch in existing_branch_names:
                data = {"default_branch": new_default_branch}
                self.requester.request_json("PATCH", f"/repos/{org_id}/{repo_name}", data)
                print_debug(f"updated default branch for '{org_id}/{repo_name}'")
            else:
                repo = self.get_repo_data(org_id, repo_name)
                default_branch = repo["default_branch"]
                data = {"new_name": new_default_branch}
                self.requester.request_json(
                    "POST", f"/repos/{org_id}/{repo_name}/branches/{default_branch}/rename", data
                )
                print_debug(f"renamed default branch for '{org_id}/{repo_name}'")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(
                f"failed to update default branch for repo '{org_id}/{repo_name}':\n{ex}"
            ).with_traceback(tb)

    def _fill_vulnerability_report(self, org_id: str, repo_name: str, repo_data: dict[str, Any]) -> None:
        print_debug(f"retrieving repo vulnerability report status for '{org_id}/{repo_name}'")

        response_vulnerability = self.requester.request_raw("GET", f"/repos/{org_id}/{repo_name}/vulnerability-alerts")

        if response_vulnerability.status_code == 204:
            repo_data["dependabot_alerts_enabled"] = True
        else:
            repo_data["dependabot_alerts_enabled"] = False

    async def _async_fill_vulnerability_report(self, org_id: str, repo_name: str, repo_data: dict[str, Any]) -> None:
        print_debug(f"async retrieving repo vulnerability report status for '{org_id}/{repo_name}'")

        status, _ = await self.requester.async_request_raw("GET", f"/repos/{org_id}/{repo_name}/vulnerability-alerts")
        if status == 204:
            repo_data["dependabot_alerts_enabled"] = True
        else:
            repo_data["dependabot_alerts_enabled"] = False

    def _update_vulnerability_report(self, org_id: str, repo_name: str, vulnerability_reports: bool) -> None:
        print_debug(f"updating repo vulnerability report status for '{org_id}/{repo_name}'")

        if vulnerability_reports is True:
            method = "PUT"
        else:
            method = "DELETE"

        response = self.requester.request_raw(method, f"/repos/{org_id}/{repo_name}/vulnerability-alerts")

        if response.status_code != 204:
            raise RuntimeError(f"failed to update vulnerability_reports for repo '{repo_name}': {response.text}")
        else:
            print_debug(f"updated vulnerability_reports for repo '{repo_name}'")

    def _fill_topics(self, org_id: str, repo_name: str, repo_data: dict[str, Any]) -> None:
        print_debug(f"retrieving repo topics for '{org_id}/{repo_name}'")

        try:
            # querying the topics might fail for temporary private forks,
            # ignore exceptions, example repo that fails:
            # https://github.com/eclipse-cbi/jiro-ghsa-wqjm-x66q-r2c6
            response = self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/topics")
            repo_data["topics"] = response.get("names", [])
        except GitHubException:
            repo_data["topics"] = []

    async def _async_fill_topics(self, org_id: str, repo_name: str, repo_data: dict[str, Any]) -> None:
        print_debug(f"async retrieving repo topics for '{org_id}/{repo_name}'")

        try:
            # querying the topics might fail for temporary private forks,
            # ignore exceptions, example repo that fails:
            # https://github.com/eclipse-cbi/jiro-ghsa-wqjm-x66q-r2c6
            response = await self.requester.async_request_json("GET", f"/repos/{org_id}/{repo_name}/topics")
            repo_data["topics"] = response.get("names", [])
        except GitHubException:
            repo_data["topics"] = []

    def _update_topics(self, org_id: str, repo_name: str, topics: list[str]) -> None:
        print_debug(f"updating repo topics for '{org_id}/{repo_name}'")

        data = {"names": topics}
        self.requester.request_json("PUT", f"/repos/{org_id}/{repo_name}/topics", data=data)
        print_debug(f"updated topics for repo '{repo_name}'")

    def get_branches(self, org_id: str, repo_name) -> list[dict[str, Any]]:
        print_debug(f"retrieving branches for repo '{org_id}/{repo_name}'")

        try:
            return self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/branches")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed getting branches for repo '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)

    def get_environments(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving environments for repo '{org_id}/{repo_name}'")

        try:
            response = self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/environments")

            environments = response["environments"]
            for env in environments:
                env_name = env["name"]
                has_branch_policies = (
                    jq.compile(".deployment_branch_policy.custom_branch_policies // false").input(env).first()
                )

                if has_branch_policies:
                    env["branch_policies"] = self._get_deployment_branch_policies(org_id, repo_name, env_name)
            return environments
        except GitHubException:
            # querying the environments might fail for private repos, ignore exceptions
            return []

    async def async_get_environments(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        print_debug(f"async retrieving environments for repo '{org_id}/{repo_name}'")

        try:
            response = await self.requester.async_request_json("GET", f"/repos/{org_id}/{repo_name}/environments")

            environments = response["environments"]
            for env in environments:
                env_name = env["name"]
                has_branch_policies = (
                    jq.compile(".deployment_branch_policy.custom_branch_policies // false").input(env).first()
                )

                if has_branch_policies:
                    env["branch_policies"] = await self._async_get_deployment_branch_policies(
                        org_id, repo_name, env_name
                    )
            return environments
        except GitHubException:
            # querying the environments might fail for private repos, ignore exceptions
            return []

    def update_environment(self, org_id: str, repo_name: str, env_name: str, env: dict[str, Any]) -> None:
        print_debug(f"updating repo environment '{env_name}' for repo '{org_id}/{repo_name}'")

        if "name" in env:
            env.pop("name")

        if "branch_policies" in env:
            branch_policies = env.pop("branch_policies")
        else:
            branch_policies = None

        try:
            self.requester.request_json("PUT", f"/repos/{org_id}/{repo_name}/environments/{env_name}", env)

            if branch_policies is not None:
                self._update_deployment_branch_policies(org_id, repo_name, env_name, branch_policies)

            print_debug(f"updated repo environment '{env_name}'")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to update repo environment '{env_name}':\n{ex}").with_traceback(tb)

    def add_environment(self, org_id: str, repo_name: str, env_name: str, data: dict[str, Any]) -> None:
        print_debug(f"adding repo environment '{env_name}' for repo '{org_id}/{repo_name}'")
        self.update_environment(org_id, repo_name, env_name, data)
        print_debug(f"added repo environment '{env_name}'")

    def delete_environment(self, org_id: str, repo_name: str, env_name: str) -> None:
        print_debug(f"deleting repo environment '{env_name} for repo '{org_id}/{repo_name}'")

        response = self.requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}/environments/{env_name}")
        if response.status_code != 204:
            raise RuntimeError(f"failed to delete repo environment '{env_name}'")

        print_debug(f"removed repo environment '{env_name}'")

    def _get_deployment_branch_policies(self, org_id: str, repo_name: str, env_name: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving deployment branch policies for env '{env_name}'")

        try:
            url = f"/repos/{org_id}/{repo_name}/environments/{env_name}/deployment-branch-policies"
            response = self.requester.request_json("GET", url)
            return response["branch_policies"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving deployment branch policies:\n{ex}").with_traceback(tb)

    async def _async_get_deployment_branch_policies(
        self, org_id: str, repo_name: str, env_name: str
    ) -> list[dict[str, Any]]:
        print_debug(f"async retrieving deployment branch policies for env '{env_name}'")

        try:
            url = f"/repos/{org_id}/{repo_name}/environments/{env_name}/deployment-branch-policies"
            response = await self.requester.async_request_json("GET", url)
            return response["branch_policies"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving deployment branch policies:\n{ex}").with_traceback(tb)

    def _update_deployment_branch_policies(
        self, org_id: str, repo_name: str, env_name: str, branch_policies: list[str]
    ) -> None:
        print_debug(f"updating deployment branch policies for env '{env_name}'")

        try:
            current_branch_policies_by_name = associate_by_key(
                self._get_deployment_branch_policies(org_id, repo_name, env_name),
                lambda x: x["name"],
            )
        except RuntimeError:
            current_branch_policies_by_name = {}

        try:
            for policy in branch_policies:
                if policy in current_branch_policies_by_name:
                    current_branch_policies_by_name.pop(policy)
                else:
                    self._create_deployment_branch_policy(org_id, repo_name, env_name, policy)

            for policy_name, policy_dict in current_branch_policies_by_name.items():
                self._delete_deployment_branch_policy(org_id, repo_name, env_name, policy_dict["id"])

            print_debug(f"updated deployment branch policies for env '{env_name}'")

        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed creating deployment branch policies:\n{ex}").with_traceback(tb)

    def _create_deployment_branch_policy(self, org_id: str, repo_name: str, env_name: str, name: str) -> None:
        print_debug(f"creating deployment branch policy for env '{env_name}' with name '{name}")

        try:
            data = {"name": name}
            url = f"/repos/{org_id}/{repo_name}/environments/{env_name}/deployment-branch-policies"
            self.requester.request_json("POST", url, data)
            print_debug(f"created deployment branch policy for env '{env_name}'")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed creating deployment branch policy:\n{ex}").with_traceback(tb)

    def _delete_deployment_branch_policy(self, org_id: str, repo_name: str, env_name: str, policy_id: int) -> None:
        print_debug(f"deleting deployment branch policy for env '{env_name}' with id '{policy_id}")

        url = f"/repos/{org_id}/{repo_name}/environments/{env_name}/deployment-branch-policies/{policy_id}"
        response = self.requester.request_raw("DELETE", url)
        if response.status_code != 204:
            raise RuntimeError(f"failed deleting deployment branch policy" f"\n{response.status_code}: {response.text}")
        else:
            print_debug(f"deleted deployment branch policy for env '{env_name}'")

    def get_secrets(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving secrets for repo '{org_id}/{repo_name}'")

        try:
            response = self.requester.request_raw("GET", f"/repos/{org_id}/{repo_name}/actions/secrets")
            if response.status_code == 200:
                return response.json()["secrets"]
            else:
                return []
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving secrets for repo '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)

    async def async_get_secrets(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        print_debug(f"async retrieving secrets for repo '{org_id}/{repo_name}'")

        try:
            status, body = await self.requester.async_request_raw("GET", f"/repos/{org_id}/{repo_name}/actions/secrets")
            if status == 200:
                return json.loads(body)["secrets"]
            else:
                return []
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving secrets for repo '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)

    def update_secret(self, org_id: str, repo_name: str, secret_name: str, secret: dict[str, Any]) -> None:
        print_debug(f"updating repo secret '{secret_name}' for repo '{org_id}/{repo_name}'")

        if "name" in secret:
            secret.pop("name")

        self.encrypt_secret_inplace(org_id, repo_name, secret)

        response = self.requester.request_raw(
            "PUT",
            f"/repos/{org_id}/{repo_name}/actions/secrets/{secret_name}",
            json.dumps(secret),
        )
        if response.status_code != 204:
            raise RuntimeError(f"failed to update repo secret '{secret_name}'")
        else:
            print_debug(f"updated repo secret '{secret_name}'")

    def add_secret(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        secret_name = data.pop("name")
        print_debug(f"adding repo secret '{secret_name}' for repo '{org_id}/{repo_name}'")

        self.encrypt_secret_inplace(org_id, repo_name, data)

        response = self.requester.request_raw(
            "PUT",
            f"/repos/{org_id}/{repo_name}/actions/secrets/{secret_name}",
            json.dumps(data),
        )
        if response.status_code != 201:
            raise RuntimeError(f"failed to add repo secret '{secret_name}'")
        else:
            print_debug(f"added repo secret '{secret_name}'")

    def encrypt_secret_inplace(self, org_id: str, repo_name: str, data: dict[str, Any]) -> None:
        value = data.pop("value")
        key_id, public_key = self.get_public_key(org_id, repo_name)
        data["encrypted_value"] = encrypt_value(public_key, value)
        data["key_id"] = key_id

    def delete_secret(self, org_id: str, repo_name: str, secret_name: str) -> None:
        print_debug(f"deleting repo secret '{secret_name}' for repo '{org_id}/{repo_name}'")

        response = self.requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}/actions/secrets/{secret_name}")
        if response.status_code != 204:
            raise RuntimeError(f"failed to delete repo secret '{secret_name}'")

        print_debug(f"removed repo secret '{secret_name}'")

    def get_variables(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving variables for repo '{org_id}/{repo_name}'")

        try:
            response = self.requester.request_raw("GET", f"/repos/{org_id}/{repo_name}/actions/variables")
            if response.status_code == 200:
                return response.json()["variables"]
            else:
                return []
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving variables for repo '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)

    async def async_get_variables(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        print_debug(f"async retrieving variables for repo '{org_id}/{repo_name}'")

        try:
            status, body = await self.requester.async_request_raw(
                "GET", f"/repos/{org_id}/{repo_name}/actions/variables"
            )
            if status == 200:
                return json.loads(body)["variables"]
            else:
                return []
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving variables for repo '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)

    def update_variable(self, org_id: str, repo_name: str, variable_name: str, variable: dict[str, Any]) -> None:
        print_debug(f"updating repo variable '{variable_name}' for repo '{org_id}/{repo_name}'")

        if "name" in variable:
            variable.pop("name")

        response = self.requester.request_raw(
            "PATCH",
            f"/repos/{org_id}/{repo_name}/actions/variables/{variable_name}",
            json.dumps(variable),
        )
        if response.status_code != 204:
            raise RuntimeError(f"failed to update repo variable '{variable_name}': {response.text}")
        else:
            print_debug(f"updated repo variable '{variable_name}'")

    def add_variable(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        variable_name = data.get("name")
        print_debug(f"adding repo variable '{variable_name}' for repo '{org_id}/{repo_name}'")

        response = self.requester.request_raw(
            "POST",
            f"/repos/{org_id}/{repo_name}/actions/variables",
            json.dumps(data),
        )
        if response.status_code != 201:
            raise RuntimeError(f"failed to add repo variable '{variable_name}': {response.text}")
        else:
            print_debug(f"added repo variable '{variable_name}'")

    def delete_variable(self, org_id: str, repo_name: str, variable_name: str) -> None:
        print_debug(f"deleting repo variable '{variable_name}' for repo '{org_id}/{repo_name}'")

        response = self.requester.request_raw(
            "DELETE", f"/repos/{org_id}/{repo_name}/actions/variables/{variable_name}"
        )
        if response.status_code != 204:
            raise RuntimeError(f"failed to delete repo variable '{variable_name}'")

        print_debug(f"removed repo variable '{variable_name}'")

    def get_workflow_settings(self, org_id: str, repo_name: str) -> dict[str, Any]:
        print_debug(f"retrieving workflow settings for repo '{org_id}/{repo_name}'")

        workflow_settings: dict[str, Any] = {}

        try:
            permissions = self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/actions/permissions")
            workflow_settings.update(permissions)
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(
                f"failed retrieving workflow settings for repo '{org_id}/{repo_name}':\n{ex}"
            ).with_traceback(tb)

        allowed_actions = permissions.get("allowed_actions", "none")
        if allowed_actions == "selected":
            workflow_settings.update(self._get_selected_actions_for_workflow_settings(org_id, repo_name))

        if permissions.get("enabled", False) is not False:
            workflow_settings.update(self._get_default_workflow_permissions(org_id, repo_name))

        return workflow_settings

    async def async_get_workflow_settings(self, org_id: str, repo_name: str) -> dict[str, Any]:
        print_debug(f"async retrieving workflow settings for repo '{org_id}/{repo_name}'")

        workflow_settings: dict[str, Any] = {}

        try:
            permissions = await self.requester.async_request_json(
                "GET", f"/repos/{org_id}/{repo_name}/actions/permissions"
            )
            workflow_settings.update(permissions)
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(
                f"failed retrieving workflow settings for repo '{org_id}/{repo_name}':\n{ex}"
            ).with_traceback(tb)

        allowed_actions = permissions.get("allowed_actions", "none")
        if allowed_actions == "selected":
            workflow_settings.update(await self._async_get_selected_actions_for_workflow_settings(org_id, repo_name))

        if permissions.get("enabled", False) is not False:
            workflow_settings.update(await self._async_get_default_workflow_permissions(org_id, repo_name))

        return workflow_settings

    def update_workflow_settings(self, org_id: str, repo_name: str, data: dict[str, Any]) -> None:
        print_debug(f"updating workflow settings for repo '{org_id}/{repo_name}'")

        permission_data = {k: data[k] for k in ["enabled", "allowed_actions"] if k in data}
        if len(permission_data) > 0:
            response = self.requester.request_raw(
                "PUT", f"/repos/{org_id}/{repo_name}/actions/permissions", json.dumps(permission_data)
            )

            if response.status_code == 204:
                print_debug(f"updated workflow settings for repo '{org_id}/{repo_name}'")
            else:
                raise RuntimeError(
                    f"failed to update workflow settings for repo '{org_id}/{repo_name}'"
                    f"\n{response.status_code}: {response.text}"
                )

        # only update the selected actions if needed
        if data.get("allowed_actions", "selected") == "selected":
            allowed_action_data = {
                k: data[k] for k in ["github_owned_allowed", "verified_allowed", "patterns_allowed"] if k in data
            }
            if len(allowed_action_data) > 0:
                self._update_selected_actions_for_workflow_settings(org_id, repo_name, allowed_action_data)

        default_permission_data = {
            k: data[k] for k in ["default_workflow_permissions", "can_approve_pull_request_reviews"] if k in data
        }
        if len(default_permission_data) > 0:
            self._update_default_workflow_permissions(org_id, repo_name, default_permission_data)

        print_debug(f"updated {len(data)} workflow setting(s)")

    def _get_selected_actions_for_workflow_settings(self, org_id: str, repo_name: str) -> dict[str, Any]:
        print_debug(f"retrieving allowed actions for org '{org_id}'")

        try:
            return self.requester.request_json(
                "GET", f"/repos/{org_id}/{repo_name}/actions/permissions/selected-actions"
            )
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(
                f"failed retrieving allowed actions for repo '{org_id}/{repo_name}':\n{ex}"
            ).with_traceback(tb)

    async def _async_get_selected_actions_for_workflow_settings(self, org_id: str, repo_name: str) -> dict[str, Any]:
        print_debug(f"async retrieving allowed actions for org '{org_id}'")

        try:
            return await self.requester.async_request_json(
                "GET", f"/repos/{org_id}/{repo_name}/actions/permissions/selected-actions"
            )
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(
                f"failed retrieving allowed actions for repo '{org_id}/{repo_name}':\n{ex}"
            ).with_traceback(tb)

    def _update_selected_actions_for_workflow_settings(self, org_id: str, repo_name: str, data: dict[str, Any]) -> None:
        print_debug(f"updating allowed actions for repo '{org_id}/{repo_name}'")

        response = self.requester.request_raw(
            "PUT", f"/repos/{org_id}/{repo_name}/actions/permissions/selected-actions", json.dumps(data)
        )

        if response.status_code == 204:
            print_debug(f"updated allowed actions for repo '{org_id}/{repo_name}'")
        else:
            raise RuntimeError(
                f"failed updating allowed actions for repo '{org_id}/{repo_name}'"
                f"\n{response.status_code}: {response.text}"
            )

    def _get_default_workflow_permissions(self, org_id: str, repo_name: str) -> dict[str, Any]:
        print_debug(f"retrieving default workflow permissions for repo '{org_id}/{repo_name}'")

        try:
            return self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/actions/permissions/workflow")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(
                f"failed retrieving default workflow permissions for repo '{org_id}/{repo_name}':\n{ex}"
            ).with_traceback(tb)

    async def _async_get_default_workflow_permissions(self, org_id: str, repo_name: str) -> dict[str, Any]:
        print_debug(f"async retrieving default workflow permissions for repo '{org_id}/{repo_name}'")

        try:
            return await self.requester.async_request_json(
                "GET", f"/repos/{org_id}/{repo_name}/actions/permissions/workflow"
            )
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(
                f"failed retrieving default workflow permissions for repo '{org_id}/{repo_name}':\n{ex}"
            ).with_traceback(tb)

    def _update_default_workflow_permissions(self, org_id: str, repo_name: str, data: dict[str, Any]) -> None:
        print_debug(f"updating default workflow permissions for repo '{org_id}/{repo_name}'")

        response = self.requester.request_raw(
            "PUT", f"/repos/{org_id}/{repo_name}/actions/permissions/workflow", json.dumps(data)
        )

        if response.status_code == 204:
            print_debug(f"updated default workflow permissions for repo '{org_id}/{repo_name}'")
        else:
            raise RuntimeError(
                f"failed updating default workflow permissions for repo '{org_id}/{repo_name}'"
                f"\n{response.status_code}: {response.text}"
            )

    def get_public_key(self, org_id: str, repo_name: str) -> tuple[str, str]:
        print_debug(f"retrieving repo public key for repo '{org_id}/{repo_name}'")

        try:
            response = self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/actions/secrets/public-key")
            return response["key_id"], response["key"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving repo public key:\n{ex}").with_traceback(tb)

    def dispatch_workflow(self, org_id: str, repo_name: str, workflow_name: str) -> bool:
        print_debug(f"dispatching workflow for repo '{org_id}/{repo_name}'")

        repo_data = self.get_repo_data(org_id, repo_name)
        data = {"ref": repo_data["default_branch"]}

        response = self.requester.request_raw(
            "POST", f"/repos/{org_id}/{repo_name}/actions/workflows/{workflow_name}/dispatches", json.dumps(data)
        )

        if response.status_code != 204:
            print_debug(f"failed dispatching workflow for repo '{org_id}/{repo_name}'")
            return False
        else:
            print_debug(f"dispatched workflow for repo '{org_id}/{repo_name}'")
            return True

    def get_ref_for_pull_request(self, org_id: str, repo_name: str, pull_number: str) -> str:
        print_debug(f"retrieving ref for pull request {pull_number} at {org_id}/{repo_name}")

        try:
            response = self.requester.request_json("GET", f"/repos/{org_id}/{repo_name}/pulls/{pull_number}")
            return response["head"]["sha"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving ref for pull request:\n{ex}").with_traceback(tb)

    def sync_from_template_repository(
        self,
        org_id: str,
        repo_name: str,
        template_repository: str,
        template_paths: Optional[list[str]],
    ) -> list[str]:
        template_owner, template_repo = re.split("/", template_repository, 1)

        updated_files = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            archive_file_name = os.path.join(tmp_dir, "archive.zip")
            with open(archive_file_name, "wb") as archive_file:
                self._download_repository_archive(archive_file, template_owner, template_repo)

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
                    print_debug(f"updating file {relative_path}")

                    with open(path, "r") as file:
                        content = file.read()

                        if str(relative_path) in template_paths_set:
                            content = self._render_template_content(org_id, repo_name, content)

                        updated = self.rest_api.content.update_content(org_id, repo_name, str(relative_path), content)
                        if updated:
                            updated_files.append(str(relative_path))

        return updated_files

    def _download_repository_archive(self, file: IO, org_id: str, repo_name: str, ref: str = "") -> None:
        print_debug(f"downloading repository archive for '{org_id}/{repo_name}'")

        try:
            with self.requester.request_raw("GET", f"/repos/{org_id}/{repo_name}/zipball/{ref}") as response:
                file.write(response.content)

        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(
                f"failed retrieving repository archive from " f"repo '{org_id}/{repo_name}':\n{ex}"
            ).with_traceback(tb)
