# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import base64
import json
import os
import pathlib
import re
import tempfile
import zipfile
from typing import Any, Optional, IO

import chevron
import jq  # type: ignore
from requests import Response
from requests_cache import CachedSession

from otterdog.utils import print_debug, print_trace, print_warn, is_set_and_present, associate_by_key
from .exception import GitHubException, BadCredentialsException


class RestClient:
    # use a fixed API version
    _GH_API_VERSION = "2022-11-28"
    _GH_API_URL_ROOT = "https://api.github.com"

    def __init__(self, token: str):
        self._requester = Requester(token, self._GH_API_URL_ROOT, self._GH_API_VERSION)

    def get_content_object(self, org_id: str, repo_name: str, path: str, ref: Optional[str] = None) -> dict[str, Any]:
        print_debug(f"retrieving content '{path}' from repo '{org_id}/{repo_name}'")

        try:
            if ref is not None:
                params = {"ref": ref}
            else:
                params = None

            return self._requester.request_json("GET",
                                                f"/repos/{org_id}/{repo_name}/contents/{path}",
                                                params=params)
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving content '{path}' from repo '{repo_name}':\n{ex}")\
                .with_traceback(tb)

    def get_content(self, org_id: str, repo_name: str, path: str, ref: Optional[str]) -> str:
        json_response = self.get_content_object(org_id, repo_name, path, ref)
        return base64.b64decode(json_response["content"]).decode('utf-8')

    def update_content(self,
                       org_id: str,
                       repo_name: str,
                       path: str,
                       content: str,
                       message: Optional[str] = None) -> bool:
        print_debug(f"putting content '{path}' to repo '{org_id}/{repo_name}'")

        try:
            json_response = self.get_content_object(org_id, repo_name, path)
            old_sha = json_response["sha"]
            old_content = base64.b64decode(json_response["content"]).decode('utf-8')
        except RuntimeError:
            old_sha = None
            old_content = None

        # check if the content has changed, otherwise do not update
        if old_content is not None and content == old_content:
            print_debug("not updating content, no changes")
            return False

        base64_encoded_data = base64.b64encode(content.encode("utf-8"))
        base64_content = base64_encoded_data.decode("utf-8")

        if message is None:
            push_message = f"Updating file '{path}' with otterdog."
        else:
            push_message = message

        data = {
            "message": push_message,
            "content": base64_content,
        }

        if old_sha is not None:
            data["sha"] = old_sha

        try:
            self._requester.request_json("PUT", f"/repos/{org_id}/{repo_name}/contents/{path}", data)
            return True
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed putting content '{path}' to repo '{repo_name}':\n{ex}").with_traceback(tb)

    def get_org_settings(self, org_id: str, included_keys: set[str]) -> dict[str, Any]:
        print_debug(f"retrieving settings for organization {org_id}")

        try:
            settings = self._requester.request_json("GET", f"/orgs/{org_id}")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving settings for organization '{org_id}':\n{ex}").with_traceback(tb)

        if "security_managers" in included_keys:
            security_managers = self.list_security_managers(org_id)
            settings["security_managers"] = security_managers

        result = {}
        for k, v in settings.items():
            if k in included_keys:
                result[k] = v
                print_trace(f"retrieved setting for '{k}' = '{v}'")

        return result

    def update_org_settings(self, org_id: str, data: dict[str, Any]) -> None:
        print_debug("updating settings via rest API")

        try:
            self._requester.request_json("PATCH", f"/orgs/{org_id}", data)
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to update settings for organization '{org_id}':\n{ex}").with_traceback(tb)

        if "security_managers" in data:
            self.update_security_managers(org_id, data["security_managers"])

        print_debug(f"updated {len(data)} setting(s)")

    def list_security_managers(self, org_id: str) -> list[str]:
        print_debug(f"retrieving security managers for organization {org_id}")

        try:
            result = self._requester.request_json("GET", f"/orgs/{org_id}/security-managers")
            return list(map(lambda x: x["slug"], result))
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving security managers for organization "
                               f"'{org_id}':\n{ex}").with_traceback(tb)

    def update_security_managers(self, org_id: str, security_managers: list[str]) -> None:
        print_debug(f"updating security managers for organization {org_id}")

        current_managers = set(self.list_security_managers(org_id))

        # first, add all security managers that are not yet configured.
        for team_slug in security_managers:
            if team_slug in current_managers:
                current_managers.remove(team_slug)
            else:
                self.add_security_manager_team(org_id, team_slug)

        # second, remove the current managers that are left.
        for team_slug in current_managers:
            self.remove_security_manager_team(org_id, team_slug)

    def add_security_manager_team(self, org_id: str, team_slug: str) -> None:
        print_debug(f"adding team {team_slug} to security managers for organization {org_id}")

        response = self._requester.request_raw("PUT", f"/orgs/{org_id}/security-managers/teams/{team_slug}")

        if response.status_code == 204:
            print_debug(f"added team {team_slug} to security managers for organization {org_id}")
        elif response.status_code == 404:
            print_warn(f"failed to add team '{team_slug}' to security managers for organization {org_id}: "
                       f"team not found")
        else:
            raise RuntimeError(f"failed adding team '{team_slug}' to security managers of organization '{org_id}'"
                               f"\n{response.status_code}: {response.text}")

    def remove_security_manager_team(self, org_id: str, team_slug: str) -> None:
        print_debug(f"removing team {team_slug} from security managers for organization {org_id}")

        response = self._requester.request_raw("DELETE", f"/orgs/{org_id}/security-managers/teams/{team_slug}")
        if response.status_code != 204:
            raise RuntimeError(f"failed removing team '{team_slug}' from security managers of organization '{org_id}'"
                               f"\n{response.status_code}: {response.text}")
        else:
            print_debug(f"removed team {team_slug} from security managers for organization {org_id}")

    def get_org_webhooks(self, org_id: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving org webhooks for org '{org_id}'")

        try:
            return self._requester.request_json("GET", f"/orgs/{org_id}/hooks")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving webhooks for org '{org_id}':\n{ex}").with_traceback(tb)

    def update_org_webhook(self, org_id: str, webhook_id: int, webhook: dict[str, Any]) -> None:
        print_debug(f"updating org webhook '{webhook_id}' for organization {org_id}")

        try:
            self._requester.request_json("PATCH", f"/orgs/{org_id}/hooks/{webhook_id}", webhook)
            print_debug(f"updated webhook {webhook_id}")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to update org webhook {webhook_id}:\n{ex}").with_traceback(tb)

    def add_org_webhook(self, org_id: str, data: dict[str, Any]) -> None:
        url = data["config"]["url"]
        print_debug(f"adding org webhook with url '{url}'")

        # mandatory field "name" = "web"
        data["name"] = "web"

        try:
            self._requester.request_json("POST", f"/orgs/{org_id}/hooks", data)
            print_debug(f"added org webhook with url '{url}'")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to add org webhook with url '{url}':\n{ex}").with_traceback(tb)

    def delete_org_webhook(self, org_id: str, webhook_id: int, url: str) -> None:
        print_debug(f"deleting org webhook with url '{url}'")

        response = self._requester.request_raw("DELETE", f"/orgs/{org_id}/hooks/{webhook_id}")

        if response.status_code != 204:
            raise RuntimeError(f"failed to delete org webhook with url '{url}'")

        print_debug(f"removed org webhook with url '{url}'")

    def get_repo_webhooks(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving webhooks for repo '{org_id}/{repo_name}'")

        try:
            # special handling due to temporary private forks for security advisories.
            #  example repo: https://github.com/eclipse-cbi/jiro-ghsa-wqjm-x66q-r2c6
            # currently it is not possible via the api to determine such repos, but when
            # requesting hooks for such a repo, you would get a 404 response.
            response = self._requester.request_raw("GET", f"/repos/{org_id}/{repo_name}/hooks")
            if response.status_code == 200:
                return response.json()
            else:
                return []
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving webhooks for repo '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)

    def update_repo_webhook(self, org_id: str, repo_name: str, webhook_id: int, webhook: dict[str, Any]) -> None:
        print_debug(f"updating repo webhook '{webhook_id}' for repo '{org_id}/{repo_name}'")

        try:
            self._requester.request_json("PATCH", f"/repos/{org_id}/{repo_name}/hooks/{webhook_id}", webhook)
            print_debug(f"updated repo webhook '{webhook_id}'")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to update repo webhook {webhook_id}:\n{ex}").with_traceback(tb)

    def add_repo_webhook(self, org_id: str, repo_name: str, data: dict[str, Any]) -> None:
        url = data["config"]["url"]
        print_debug(f"adding repo webhook with url '{url}' for repo '{org_id}/{repo_name}'")

        # mandatory field "name" = "web"
        data["name"] = "web"

        try:
            self._requester.request_json("POST", f"/repos/{org_id}/{repo_name}/hooks", data)
            print_debug(f"added repo webhook with url '{url}'")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to add repo webhook with url '{url}':\n{ex}").with_traceback(tb)

    def delete_repo_webhook(self, org_id: str, repo_name: str, webhook_id: int, url: str) -> None:
        print_debug(f"deleting repo webhook with url '{url}' for repo '{org_id}/{repo_name}'")

        response = self._requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}/hooks/{webhook_id}")

        if response.status_code != 204:
            raise RuntimeError(f"failed to delete repo webhook with url '{url}'")

        print_debug(f"removed repo webhook with url '{url}'")

    def get_repos(self, org_id: str) -> list[str]:
        print_debug(f"retrieving repos for organization {org_id}")

        params = {"type": "all"}
        try:
            repos = self._requester.request_paged_json("GET", f"/orgs/{org_id}/repos", params)
            return [repo["name"] for repo in repos]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to retrieve repos for organization '{org_id}':\n{ex}").with_traceback(tb)

    def get_repo_data(self, org_id: str, repo_name: str) -> dict[str, Any]:
        print_debug(f"retrieving org repo data for '{org_id}/{repo_name}'")

        try:
            repo_data = self._requester.request_json("GET", f"/repos/{org_id}/{repo_name}")
            self._fill_vulnerability_report_for_repo(org_id, repo_name, repo_data)
            self._fill_topics_for_repo(org_id, repo_name, repo_data)
            return repo_data
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving data for repo '{repo_name}':\n{ex}").with_traceback(tb)

    def update_repo(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
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

        if changes > 0:
            try:
                if len(data) > 0:
                    self._requester.request_json("PATCH", f"/repos/{org_id}/{repo_name}", data)

                if vulnerability_reports is not None:
                    self._update_vulnerability_report_for_repo(org_id, repo_name, vulnerability_reports)
                if topics is not None:
                    self._update_topics_for_repo(org_id, repo_name, topics)

                print_debug(f"updated {changes} repo setting(s) for repo '{repo_name}'")
            except GitHubException as ex:
                tb = ex.__traceback__
                raise RuntimeError(f"failed to update settings for repo '{repo_name}':\n{ex}").with_traceback(tb)

    def add_repo(self,
                 org_id: str,
                 data: dict[str, Any],
                 template_repository: Optional[str],
                 post_process_template_content: list[str],
                 auto_init_repo: bool) -> None:
        repo_name = data["name"]

        if is_set_and_present(template_repository):
            print_debug(f"creating repo '{org_id}/{repo_name}' with template '{template_repository}'")
            template_owner, template_repo = re.split("/", template_repository, 1)

            try:
                template_data = {
                    "owner": org_id,
                    "name": repo_name,
                    "include_all_branches": False,
                    "private": data.get("private", False)
                }

                self._requester.request_json("POST",
                                             f"/repos/{template_owner}/{template_repo}/generate",
                                             template_data)

                print_debug(f"created repo with name '{repo_name}' from template '{template_repository}'")

                # get all the data for the created repo to avoid setting values that can not be changed due
                # to defaults from the organization (like web_commit_signoff_required)
                current_data = self.get_repo_data(org_id, repo_name)
                self._remove_already_active_settings(data, current_data)
                self.update_repo(org_id, repo_name, data)

                # wait till the repo is initialized, this might take a while.
                if len(post_process_template_content) > 0:
                    for i in range(1, 4):
                        try:
                            self.get_readme_of_repo(org_id, repo_name)
                            break
                        except GitHubException:
                            print_trace(f"waiting for repo '{org_id}/{repo_name}' to be initialized, "
                                        f"try {i} of 3")
                            import time
                            time.sleep(1)

                # if there is template content which shall be post-processed,
                # use chevron to expand some variables that might be used there.
                for content_path in post_process_template_content:
                    content = self.get_content(org_id, repo_name, content_path, None)
                    updated_content = self._render_template_content(org_id, repo_name, content)
                    if content != updated_content:
                        self.update_content(org_id, repo_name, content_path, updated_content)

                return
            except GitHubException as ex:
                tb = ex.__traceback__
                raise RuntimeError(
                    f"failed to create repo from template '{template_repository}':\n{ex}").with_traceback(tb)

        print_debug(f"creating repo '{org_id}/{repo_name}'")

        # some settings do not seem to be set correctly during creation
        # collect them and update the repo after creation.
        update_keys = ['dependabot_alerts_enabled', 'web_commit_signoff_required', 'security_and_analysis', 'topics']
        update_data = {}

        for update_key in update_keys:
            if update_key in data:
                update_data[update_key] = data.pop(update_key)

        # whether the repo should be initialized with an empty README
        data["auto_init"] = auto_init_repo

        try:
            result = self._requester.request_json("POST", f"/orgs/{org_id}/repos", data)
            print_debug(f"created repo with name '{repo_name}'")
            self._remove_already_active_settings(update_data, result)
            self.update_repo(org_id, repo_name, update_data)
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to add repo with name '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)

    @staticmethod
    def _render_template_content(org_id: str, repo_name: str, content: str) -> str:
        variables = {
            "org": org_id,
            "repo": repo_name
        }

        return chevron.render(content, variables)

    def get_readme_of_repo(self, org_id: str, repo_name: str) -> dict[str, Any]:
        print_debug(f"getting readme for repo '{org_id}/{repo_name}'")

        try:
            return self._requester.request_json("GET", f"/repos/{org_id}/{repo_name}/readme")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to get readme for repo '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)

    def delete_repo(self, org_id: str, repo_name: str) -> None:
        print_debug(f"deleting repo '{org_id}/{repo_name}'")

        response = self._requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}")

        if response.status_code != 204:
            raise RuntimeError(f"failed to delete repo '{org_id}/{repo_name}'")

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

    def _fill_vulnerability_report_for_repo(self, org_id: str, repo_name: str, repo_data: dict[str, Any]) -> None:
        print_debug(f"retrieving repo vulnerability report status for '{org_id}/{repo_name}'")

        response_vulnerability = \
            self._requester.request_raw("GET", f"/repos/{org_id}/{repo_name}/vulnerability-alerts")

        if response_vulnerability.status_code == 204:
            repo_data["dependabot_alerts_enabled"] = True
        else:
            repo_data["dependabot_alerts_enabled"] = False

    def _update_vulnerability_report_for_repo(self, org_id: str, repo_name: str, vulnerability_reports: bool) -> None:
        print_debug(f"updating repo vulnerability report status for '{org_id}/{repo_name}'")

        if vulnerability_reports is True:
            method = "PUT"
        else:
            method = "DELETE"

        response = self._requester.request_raw(method, f"/repos/{org_id}/{repo_name}/vulnerability-alerts")

        if response.status_code != 204:
            raise RuntimeError(f"failed to update vulnerability_reports for repo '{repo_name}'")
        else:
            print_debug(f"updated vulnerability_reports for repo '{repo_name}'")

    def _fill_topics_for_repo(self, org_id: str, repo_name: str, repo_data: dict[str, Any]) -> None:
        print_debug(f"retrieving repo topics for '{org_id}/{repo_name}'")

        try:
            # querying the topics might fail for temporary private forks,
            # ignore exceptions, example repo that fails:
            # https://github.com/eclipse-cbi/jiro-ghsa-wqjm-x66q-r2c6
            response = \
                self._requester.request_json("GET", f"/repos/{org_id}/{repo_name}/topics")
            repo_data["topics"] = response.get("names", [])
        except GitHubException:
            repo_data["topics"] = []

    def _update_topics_for_repo(self, org_id: str, repo_name: str, topics: list[str]) -> None:
        print_debug(f"updating repo topics for '{org_id}/{repo_name}'")

        data = {"names": topics}
        self._requester.request_json("PUT", f"/repos/{org_id}/{repo_name}/topics", data=data)
        print_debug(f"updated topics for repo '{repo_name}'")

    def get_repo_environments(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving environments for repo '{org_id}/{repo_name}'")

        try:
            response = self._requester.request_json("GET", f"/repos/{org_id}/{repo_name}/environments")

            environments = response["environments"]
            for env in environments:
                env_name = env["name"]
                has_branch_policies = \
                    jq.compile(".deployment_branch_policy.custom_branch_policies // false").input(env).first()

                if has_branch_policies:
                    env["branch_policies"] = self._get_deployment_branch_policies(org_id, repo_name, env_name)
            return environments
        except GitHubException:
            # querying the environments might fail for private repos, ignore exceptions
            return []

    def update_repo_environment(self, org_id: str, repo_name: str, env_name: str, env: dict[str, Any]) -> None:
        print_debug(f"updating repo environment '{env_name}' for repo '{org_id}/{repo_name}'")

        if "name" in env:
            env.pop("name")

        if "branch_policies" in env:
            branch_policies = env.pop("branch_policies")
        else:
            branch_policies = None

        try:
            self._requester.request_json("PUT", f"/repos/{org_id}/{repo_name}/environments/{env_name}", env)

            if branch_policies is not None:
                self._update_deployment_branch_policies(org_id, repo_name, env_name, branch_policies)

            print_debug(f"updated repo environment '{env_name}'")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to update repo environment '{env_name}':\n{ex}").with_traceback(tb)

    def add_repo_environment(self, org_id: str, repo_name: str, env_name: str, data: dict[str, Any]) -> None:
        print_debug(f"adding repo environment '{env_name}' for repo '{org_id}/{repo_name}'")
        self.update_repo_environment(org_id, repo_name, env_name, data)
        print_debug(f"added repo environment '{env_name}'")

    def delete_repo_environment(self, org_id: str, repo_name: str, env_name: str) -> None:
        print_debug(f"deleting repo environment '{env_name} for repo '{org_id}/{repo_name}'")

        response = self._requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}/environments/{env_name}")
        if response.status_code != 204:
            raise RuntimeError(f"failed to delete repo environment '{env_name}'")

        print_debug(f"removed repo environment '{env_name}'")

    def _get_deployment_branch_policies(self, org_id: str, repo_name: str, env_name: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving deployment branch policies for env '{env_name}'")

        try:
            url = f"/repos/{org_id}/{repo_name}/environments/{env_name}/deployment-branch-policies"
            response = self._requester.request_json("GET", url)
            return response["branch_policies"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving deployment branch policies:\n{ex}").with_traceback(tb)

    def _update_deployment_branch_policies(self,
                                           org_id: str,
                                           repo_name: str,
                                           env_name: str,
                                           branch_policies: list[str]) -> None:
        print_debug(f"updating deployment branch policies for env '{env_name}'")

        current_branch_policies_by_name = \
            associate_by_key(self._get_deployment_branch_policies(org_id, repo_name, env_name),
                             lambda x: x["name"])

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

    def _create_deployment_branch_policy(self,
                                         org_id: str,
                                         repo_name: str,
                                         env_name: str,
                                         name: str) -> None:
        print_debug(f"creating deployment branch policy for env '{env_name}' with name '{name}")

        try:
            data = {"name": name}
            url = f"/repos/{org_id}/{repo_name}/environments/{env_name}/deployment-branch-policies"
            self._requester.request_json("POST", url, data)
            print_debug(f"created deployment branch policy for env '{env_name}'")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed creating deployment branch policy:\n{ex}").with_traceback(tb)

    def _delete_deployment_branch_policy(self,
                                         org_id: str,
                                         repo_name: str,
                                         env_name: str,
                                         policy_id: int) -> None:
        print_debug(f"deleting deployment branch policy for env '{env_name}' with id '{policy_id}")

        url = f"/repos/{org_id}/{repo_name}/environments/{env_name}/deployment-branch-policies/{policy_id}"
        response = self._requester.request_raw("DELETE", url)
        if response.status_code != 204:
            raise RuntimeError(
                f"failed deleting deployment branch policy"
                f"\n{response.status_code}: {response.text}")
        else:
            print_debug(f"deleted deployment branch policy for env '{env_name}'")

    def get_org_secrets(self, org_id: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving secrets for org '{org_id}'")

        try:
            response = self._requester.request_json("GET", f"/orgs/{org_id}/actions/secrets")

            secrets = response["secrets"]
            for secret in secrets:
                if secret["visibility"] == "selected":
                    secret["selected_repositories"] = \
                        self._get_selected_repositories_for_org_secret(org_id, secret["name"])
            return secrets
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed getting secrets for org '{org_id}':\n{ex}").with_traceback(tb)

    def _get_selected_repositories_for_org_secret(self, org_id: str, secret_name: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving selected repositories secret '{secret_name}'")

        try:
            url = f"/orgs/{org_id}/actions/secrets/{secret_name}/repositories"
            response = self._requester.request_json("GET", url)
            return response["repositories"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving selected repositories:\n{ex}").with_traceback(tb)

    def update_org_secret(self, org_id: str, secret_name: str, secret: dict[str, Any]) -> None:
        print_debug(f"updating org secret '{secret_name}'")

        if "name" in secret:
            secret.pop("name")

        self.encrypt_org_secret_inplace(org_id, secret)

        response = \
            self._requester.request_raw("PUT",
                                        f"/orgs/{org_id}/actions/secrets/{secret_name}",
                                        json.dumps(secret))
        if response.status_code != 204:
            raise RuntimeError(f"failed to update org secret '{secret_name}'")
        else:
            print_debug(f"updated org secret '{secret_name}'")

    def add_org_secret(self, org_id: str, data: dict[str, str]) -> None:
        secret_name = data.pop("name")
        print_debug(f"adding org secret '{secret_name}'")

        self.encrypt_org_secret_inplace(org_id, data)

        response = \
            self._requester.request_raw("PUT",
                                        f"/orgs/{org_id}/actions/secrets/{secret_name}",
                                        json.dumps(data))
        if response.status_code != 201:
            raise RuntimeError(f"failed to add org secret '{secret_name}'")
        else:
            print_debug(f"added org secret '{secret_name}'")

    def encrypt_org_secret_inplace(self, org_id: str, data: dict[str, Any]) -> None:
        value = data.pop("value")
        key_id, public_key = self.get_org_public_key(org_id)
        data["encrypted_value"] = self.encrypt_value(public_key, value)
        data["key_id"] = key_id

    def delete_org_secret(self, org_id: str, secret_name: str) -> None:
        print_debug(f"deleting org secret '{secret_name}'")

        response = self._requester.request_raw("DELETE", f"/orgs/{org_id}/actions/secrets/{secret_name}")
        if response.status_code != 204:
            raise RuntimeError(f"failed to delete org secret '{secret_name}'")

        print_debug(f"removed org secret '{secret_name}'")

    def get_repo_secrets(self, org_id: str, repo_name: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving secrets for repo '{org_id}/{repo_name}'")

        try:
            response = self._requester.request_json("GET", f"/repos/{org_id}/{repo_name}/actions/secrets")
            return response["secrets"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed getting secrets for repo '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)

    def update_repo_secret(self, org_id: str, repo_name: str, secret_name: str, secret: dict[str, Any]) -> None:
        print_debug(f"updating repo secret '{secret_name}' for repo '{org_id}/{repo_name}'")

        if "name" in secret:
            secret.pop("name")

        self.encrypt_repo_secret_inplace(org_id, repo_name, secret)

        response = \
            self._requester.request_raw("PUT",
                                        f"/repos/{org_id}/{repo_name}/actions/secrets/{secret_name}",
                                        json.dumps(secret))
        if response.status_code != 204:
            raise RuntimeError(f"failed to update repo secret '{secret_name}'")
        else:
            print_debug(f"updated repo secret '{secret_name}'")

    def add_repo_secret(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        secret_name = data.pop("name")
        print_debug(f"adding repo secret '{secret_name}' for repo '{org_id}/{repo_name}'")

        self.encrypt_repo_secret_inplace(org_id, repo_name, data)

        response = \
            self._requester.request_raw("PUT",
                                        f"/repos/{org_id}/{repo_name}/actions/secrets/{secret_name}",
                                        json.dumps(data))
        if response.status_code != 201:
            raise RuntimeError(f"failed to add repo secret '{secret_name}'")
        else:
            print_debug(f"added repo secret '{secret_name}'")

    def encrypt_repo_secret_inplace(self, org_id: str, repo_name: str, data: dict[str, Any]) -> None:
        value = data.pop("value")
        key_id, public_key = self.get_repo_public_key(org_id, repo_name)
        data["encrypted_value"] = self.encrypt_value(public_key, value)
        data["key_id"] = key_id

    def delete_repo_secret(self, org_id: str, repo_name: str, secret_name: str) -> None:
        print_debug(f"deleting repo secret '{secret_name}' for repo '{org_id}/{repo_name}'")

        response = self._requester.request_raw("DELETE", f"/repos/{org_id}/{repo_name}/actions/secrets/{secret_name}")
        if response.status_code != 204:
            raise RuntimeError(f"failed to delete repo secret '{secret_name}'")

        print_debug(f"removed repo secret '{secret_name}'")

    @staticmethod
    def encrypt_value(public_key: str, secret_value: str) -> str:
        """
        Encrypt a Unicode string using a public key.
        """
        from base64 import b64encode
        from nacl import encoding, public

        public_key_obj = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder)
        sealed_box = public.SealedBox(public_key_obj)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        return b64encode(encrypted).decode("utf-8")

    def get_org_public_key(self, org_id: str) -> tuple[str, str]:
        print_debug(f"retrieving org public key for org '{org_id}'")

        try:
            response = self._requester.request_json("GET", f"/orgs/{org_id}/actions/secrets/public-key")
            return response["key_id"], response["key"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving org public key:\n{ex}").with_traceback(tb)

    def get_repo_public_key(self, org_id: str, repo_name: str) -> tuple[str, str]:
        print_debug(f"retrieving repo public key for repo '{org_id}/{repo_name}'")

        try:
            response = self._requester.request_json("GET", f"/repos/{org_id}/{repo_name}/actions/secrets/public-key")
            return response["key_id"], response["key"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving repo public key:\n{ex}").with_traceback(tb)

    def get_user_ids(self, login: str) -> tuple[int, str]:
        print_debug(f"retrieving user ids for user '{login}'")

        try:
            response = self._requester.request_json("GET", f"/users/{login}")
            return response["id"], response["node_id"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving user node id:\n{ex}").with_traceback(tb)

    def get_team_ids(self, combined_slug: str) -> tuple[int, str]:
        print_debug("retrieving team ids")
        org_id, team_slug = re.split("/", combined_slug)

        try:
            response = self._requester.request_json("GET", f"/orgs/{org_id}/teams/{team_slug}")
            return response["id"], response["node_id"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving team node id:\n{ex}").with_traceback(tb)

    def get_app_ids(self, app_slug: str) -> tuple[int, str]:
        print_debug("retrieving app node id")

        try:
            response = self._requester.request_json("GET", f"/apps/{app_slug}")
            return response["id"], response["node_id"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving app node id:\n{ex}").with_traceback(tb)

    def get_ref_for_pull_request(self, org_id: str, repo_name: str, pull_number: str) -> str:
        print_debug(f"retrieving ref for pull request {pull_number} at {org_id}/{repo_name}")

        try:
            response = self._requester.request_json("GET", f"/repos/{org_id}/{repo_name}/pulls/{pull_number}")
            return response["head"]["sha"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving ref for pull request:\n{ex}").with_traceback(tb)

    def sync_from_template_repository(self,
                                      org_id: str,
                                      repo_name: str,
                                      template_repository: str,
                                      template_paths: Optional[list[str]]) -> list[str]:
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

                        updated = self.update_content(org_id, repo_name, str(relative_path), content)
                        if updated:
                            updated_files.append(str(relative_path))

        return updated_files

    def _download_repository_archive(self, file: IO, org_id: str, repo_name: str, ref: str = "") -> None:
        print_debug(f"downloading repository archive for '{org_id}/{repo_name}'")

        try:
            response = \
                self._requester.request_raw("GET",
                                            f"/repos/{org_id}/{repo_name}/zipball/{ref}",
                                            stream=True)

            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving repository archive from "
                               f"repo '{org_id}/{repo_name}':\n{ex}").with_traceback(tb)


class Requester:
    def __init__(self, token: str, base_url: str, api_version: str):
        self._base_url = base_url

        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": api_version,
            "X-Github-Next-Global-ID": "1"
        }

        # enable logging for requests_cache
        # import logging
        # logging.basicConfig(level='DEBUG')

        self._session: CachedSession = \
            CachedSession("otterdog",
                          backend="filesystem",
                          use_cache_dir=True,
                          cache_control=True,
                          allowable_methods=['GET'])

    def _build_url(self, url_path: str) -> str:
        return f"{self._base_url}{url_path}"

    def request_paged_json(self,
                           method: str,
                           url_path: str,
                           data: Optional[dict[str, Any]] = None,
                           params: Optional[dict[str, str]] = None) -> list[dict[str, Any]]:
        result = []
        current_page = 1
        while current_page > 0:
            query_params = {"per_page": "100", "page": current_page}
            if params is not None:
                query_params.update(params)

            response: list[dict[str, Any]] = self.request_json(method, url_path, data, query_params)

            if len(response) == 0:
                current_page = -1
            else:
                for item in response:
                    result.append(item)

                current_page += 1

        return result

    def request_json(self,
                     method: str,
                     url_path: str,
                     data: Optional[dict[str, Any]] = None,
                     params: Optional[dict[str, Any]] = None) -> Any:
        input_data = None
        if data is not None:
            input_data = json.dumps(data)

        response = self.request_raw(method, url_path, input_data, params)
        self._check_response(response)
        return response.json()

    def request_raw(self,
                    method: str,
                    url_path: str,
                    data: Optional[str] = None,
                    params: Optional[dict[str, str]] = None,
                    stream: bool = False) -> Response:
        assert method in ["GET", "PATCH", "POST", "PUT", "DELETE"]

        response = \
            self._session.request(method,
                                  url=self._build_url(url_path),
                                  headers=self._headers,
                                  refresh=True,
                                  params=params,
                                  data=data,
                                  stream=stream)

        print_trace(f"'{method}' result = ({response.status_code}, {response.text})")

        return response

    def _check_response(self, response: Response) -> None:
        if response.status_code >= 400:
            self._create_exception(response)

    @staticmethod
    def _create_exception(response: Response):
        status = response.status_code
        url = response.request.url

        if status == 401:
            raise BadCredentialsException(url, status, response.text)
        else:
            raise GitHubException(url, status, response.text)
