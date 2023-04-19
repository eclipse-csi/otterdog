#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

import base64
import json
import re
from typing import Any

from requests import Response
from requests_cache import CachedSession

from otterdog import utils

from .exception import *


class RestClient:
    # use a fixed API version
    _GH_API_VERSION = "2022-11-28"
    _GH_API_URL_ROOT = "https://api.github.com"

    def __init__(self, token: str):
        self._requester = Requester(token, self._GH_API_URL_ROOT, self._GH_API_VERSION)

    def get_content_object(self, org_id: str, repo_name: str, path: str) -> dict[str, Any]:
        utils.print_debug(f"retrieving content '{path}' from repo '{repo_name}'")

        try:
            return self._requester.request_json("GET", f"/repos/{org_id}/{repo_name}/contents/{path}")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving content '{path}' from repo '{repo_name}':\n{ex}").with_traceback(tb)

    def get_content(self, org_id: str, repo_name: str, path: str) -> str:
        json_response = self.get_content_object(org_id, repo_name, path)
        return base64.b64decode(json_response["content"]).decode('utf-8')

    def update_content(self, org_id: str, repo_name: str, path: str, content: str) -> None:
        utils.print_debug(f"putting content '{path}' to repo '{repo_name}'")

        try:
            json_response = self.get_content_object(org_id, repo_name, path)
            old_sha = json_response["sha"]
            old_content = base64.b64decode(json_response["content"]).decode('utf-8')
        except RuntimeError:
            old_sha = None
            old_content = None

        # check if the content has changed, otherwise do not update
        if old_content is not None and content == old_content:
            utils.print_debug(f"not updating content, no changes")
            return

        base64_encoded_data = base64.b64encode(content.encode("utf-8"))
        base64_content = base64_encoded_data.decode("utf-8")

        data = {
            "message": f"Updating file '{path}' with otterdog.",
            "content": base64_content,
        }

        if old_sha is not None:
            data["sha"] = old_sha

        try:
            self._requester.request_json("PUT", f"/repos/{org_id}/{repo_name}/contents/{path}", data)
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed putting content '{path}' to repo '{repo_name}':\n{ex}").with_traceback(tb)

    def get_org_settings(self, org_id: str, included_keys: set[str]) -> dict[str, str]:
        utils.print_debug(f"retrieving settings for organization {org_id}")

        try:
            settings = self._requester.request_json("GET", f"/orgs/{org_id}")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving settings for organization '{org_id}':\n{ex}").with_traceback(tb)

        result = {}
        for k, v in settings.items():
            if k in included_keys:
                result[k] = v
                utils.print_trace(f"retrieved setting for '{k}' = '{v}'")

        return result

    def update_org_settings(self, org_id: str, data: dict[str, str]) -> None:
        utils.print_debug("updating settings via rest API")

        try:
            self._requester.request_json("PATCH", f"/orgs/{org_id}", data)
            utils.print_debug(f"updated {len(data)} setting(s)")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to update settings for organization '{org_id}':\n{ex}").with_traceback(tb)

    def get_webhooks(self, org_id: str) -> list[dict[str, Any]]:
        utils.print_debug(f"retrieving org webhooks for organization {org_id}")

        try:
            return self._requester.request_json("GET", f"/orgs/{org_id}/hooks")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving webhooks for organization '{org_id}':\n{ex}").with_traceback(tb)

    def update_webhook(self, org_id: str, webhook_id: str, webhook: dict[str, Any]) -> None:
        utils.print_debug(f"updating webhook {webhook_id} for organization {org_id}")

        try:
            self._requester.request_json("PATCH", f"/orgs/{org_id}/hooks/{webhook_id}", webhook)
            utils.print_debug(f"updated webhook {webhook_id}")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to update webhook {webhook_id}:\n{ex}").with_traceback(tb)

    def add_webhook(self, org_id: str, data: dict[str, Any]) -> None:
        url = data["config"]["url"]
        utils.print_debug(f"adding webhook with url '{url}'")

        # mandatory field "name" = "web"
        data["name"] = "web"

        try:
            self._requester.request_json("POST", f"/orgs/{org_id}/hooks", data)
            utils.print_debug(f"added webhook with url '{url}'")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to add webhook with url '{url}':\n{ex}").with_traceback(tb)

    def get_repos(self, org_id: str) -> list[str]:
        utils.print_debug("retrieving org repos via rest API")

        params = {"type": "all"}
        try:
            repos = self._requester.request_paged_json("GET", f"/orgs/{org_id}/repos", params)

            def get_name(data: dict[str, str]) -> str:
                return data["name"]

            return list(map(get_name, repos))
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to retrieve repos for organization '{org_id}':\n{ex}").with_traceback(tb)

    def get_repo_data(self, org_id: str, repo_name: str) -> dict[str, Any]:
        utils.print_debug(f"retrieving org repo data for '{repo_name}'")

        try:
            repo_data = self._requester.request_json("GET", f"/repos/{org_id}/{repo_name}")
            self._fill_vulnerability_report_for_repo(org_id, repo_name, repo_data)
            return repo_data
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving data for repo '{repo_name}':\n{ex}").with_traceback(tb)

    def update_repo(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        utils.print_debug(f"updating repo settings for repo '{repo_name}'")

        changes = len(data)

        if "dependabot_alerts_enabled" in data:
            vulnerability_reports = bool(data.pop("dependabot_alerts_enabled"))
        else:
            vulnerability_reports = None

        if changes > 0:
            try:
                if len(data) > 0:
                    self._requester.request_json("PATCH", f"/repos/{org_id}/{repo_name}", data)
                if vulnerability_reports is not None:
                    self._update_vulnerability_report_for_repo(org_id, repo_name, vulnerability_reports)
                utils.print_debug(f"updated {changes} repo setting(s) for repo '{repo_name}'")
            except GitHubException as ex:
                tb = ex.__traceback__
                raise RuntimeError(f"failed to update settings for repo '{repo_name}':\n{ex}").with_traceback(tb)

    def add_repo(self, org_id: str, data: dict[str, Any], auto_init_repo: bool) -> None:
        repo_name = data["name"]
        utils.print_debug(f"creating repo '{repo_name}'")

        # some settings do not seem to be set correctly during creation
        # collect them and update the repo after creation.
        update_keys = ['dependabot_alerts_enabled', 'web_commit_signoff_required', 'security_and_analysis']
        update_data = {}

        for update_key in update_keys:
            if update_key in data:
                update_data[update_key] = data.pop(update_key)

        # whether the repo should be initialized with an empty README
        data["auto_init"] = auto_init_repo

        try:
            self._requester.request_json("POST", f"/orgs/{org_id}/repos", data)
            utils.print_debug(f"added repo with name '{repo_name}'")
            self.update_repo(org_id, repo_name, update_data)
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to add repo with name '{repo_name}':\n{ex}").with_traceback(tb)

    def _fill_vulnerability_report_for_repo(self, org_id: str, repo_name: str, repo_data: dict[str, Any]) -> None:
        utils.print_debug(f"retrieving repo vulnerability report status for '{repo_name}'")

        response_vulnerability = \
            self._requester.request_raw("GET", f"/repos/{org_id}/{repo_name}/vulnerability-alerts")

        if response_vulnerability.status_code == 204:
            repo_data["dependabot_alerts_enabled"] = True
        else:
            repo_data["dependabot_alerts_enabled"] = False

    def _update_vulnerability_report_for_repo(self, org_id: str, repo_name: str, vulnerability_reports: bool) -> None:
        utils.print_debug(f"updating repo vulnerability report status for '{repo_name}'")

        if vulnerability_reports is True:
            method = "PUT"
        else:
            method = "DELETE"

        response = self._requester.request_raw(method, f"/repos/{org_id}/{repo_name}/vulnerability-alerts")

        if response.status_code != 204:
            raise RuntimeError(f"failed to update vulnerability_reports for repo '{repo_name}'")
        else:
            utils.print_debug(f"updated vulnerability_reports for repo '{repo_name}'")

    def get_user_node_id(self, login: str):
        utils.print_debug(f"retrieving user node id for user '{login}'")

        try:
            response = self._requester.request_json("GET", f"/users/{login}")
            return response["node_id"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving user node id:\n{ex}").with_traceback(tb)

    def get_team_node_id(self, combined_slug: str) -> str:
        utils.print_debug("retrieving team node id via rest API")
        org_id, team_slug = re.split("/", combined_slug)

        try:
            response = self._requester.request_json("GET", f"/orgs/{org_id}/teams/{team_slug}")
            return response["node_id"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving team node id:\n{ex}").with_traceback(tb)


class Requester:
    def __init__(self, token: str, base_url: str, api_version: str):
        self._base_url = base_url

        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": api_version
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
                           data: dict[str, Any] = None,
                           params: dict[str, str] = None) -> list[dict[str, str]]:
        result = []
        current_page = 1
        while current_page > 0:
            query_params = {"per_page": "100", "page": current_page}
            if params is not None:
                query_params.update(params)

            response = self.request_json(method, url_path, data, query_params)

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
                     data: dict[str, Any] = None,
                     params: dict[str, str] = None) -> dict[str, Any] | list[dict[str, Any]]:
        input_data = None
        if data is not None:
            input_data = json.dumps(data)

        response = self.request_raw(method, url_path, input_data, params)
        self._check_response(response)
        return response.json()

    def request_raw(self,
                    method: str,
                    url_path: str,
                    data: str = None,
                    params: dict[str, str] = None) -> Response:
        assert method in ["GET", "PATCH", "POST", "PUT", "DELETE"]

        response = \
            self._session.request(method,
                                  url=self._build_url(url_path),
                                  headers=self._headers,
                                  params=params,
                                  data=data)

        utils.print_trace(f"'{method}' result = ({response.status_code}, {response.text})")

        return response

    def _check_response(self, response: Response) -> None:
        if response.status_code >= 400:
            self._create_exception(response)

    @staticmethod
    def _create_exception(response: Response):
        status = response.status_code
        url = response.request.url

        if status == 401:
            raise BadCredentialsException(url, status, response.text, response.headers)
        else:
            raise GitHubException(url, status, response.text, response.headers)
