# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
from typing import Any

import requests

import utils


class GithubRest:
    # use a fixed API version
    _GH_API_VERSION = "2022-11-28"
    _GH_API_URL_ROOT = "https://api.github.com"

    def __init__(self, token: str):
        self._token = token

        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": self._GH_API_VERSION
        }

    def get_org_settings(self, org_id: str, included_keys: set[str]) -> dict[str, str]:
        utils.print_debug("retrieving settings via rest API")
        response = requests.get(url=f"{self._GH_API_URL_ROOT}/orgs/{org_id}", headers=self._headers)
        utils.print_trace(f"rest result = ({response.status_code}, {response.text})")

        if not response.ok:
            msg = f"failed retrieving settings for organization '{org_id}' via rest API"
            utils.exit_with_message(msg, 1)

        json_output = response.json()
        result = {}
        for k, v in json_output.items():
            if k in included_keys:
                result[k] = v
                utils.print_trace(f"retrieved setting for '{k}' = '{v}'")

        return result

    def update_org_settings(self, org_id: str, data: dict[str, str]) -> None:
        utils.print_debug("updating settings via rest API")
        response = requests.patch(url=f"{self._GH_API_URL_ROOT}/orgs/{org_id}",
                                  headers=self._headers,
                                  data=json.dumps(data))
        utils.print_trace(f"{response.request.url} {response.request.headers} {response.request.body}")
        utils.print_trace(f"rest result = ({response.status_code}, {response.text})")

        if not response.ok:
            utils.exit_with_message(f"failed to update settings for organization '{org_id}'", 1)

        utils.print_debug(f"updated {len(data)} setting(s) via rest api")

    def get_webhooks(self, org_id: str) -> list[dict[str, Any]]:
        utils.print_debug("retrieving org webhooks via rest API")
        response = requests.get(url=f"{self._GH_API_URL_ROOT}/orgs/{org_id}/hooks", headers=self._headers)
        utils.print_trace(f"rest result = ({response.status_code}, {response.text})")

        if not response.ok:
            msg = f"failed retrieving webhooks for organization '{org_id}' via rest API"
            utils.exit_with_message(msg, 1)

        return response.json()

    def update_webhook_config(self, org_id: str, webhook_id: str, config: dict[str, str]) -> None:
        utils.print_debug("updating webhook configuration via rest API")

        response = requests.patch(url=f"{self._GH_API_URL_ROOT}/orgs/{org_id}/hooks/{webhook_id}/config",
                                  headers=self._headers,
                                  data=json.dumps(config))
        utils.print_trace(f"rest result = ({response.status_code}, {response.text})")

        if not response.ok:
            utils.exit_with_message(f"failed to update config for webhook '{webhook_id}'", 1)

        utils.print_debug(f"updated {len(config)} webhook setting(s) via rest api")

    def add_webhook(self, org_id: str, data: dict[str, Any]) -> None:
        url = data["config"]["url"]
        utils.print_debug("adding webhook via rest API")

        # mandatory field "name" = "web"
        data["name"] = "web"

        response = requests.post(url=f"{self._GH_API_URL_ROOT}/orgs/{org_id}/hooks",
                                 headers=self._headers,
                                 data=json.dumps(data))
        utils.print_trace(f"rest result = ({response.status_code}, {response.text})")

        if not response.ok:
            utils.exit_with_message(f"failed to add webhook with url '{url}'", 1)

        utils.print_debug(f"added webhook with url '{url}' via rest api")

    def get_repos(self, org_id: str) -> list[dict[str, Any]]:
        utils.print_debug("retrieving org repos via rest API")

        repos = []
        current_page = 1
        while current_page > 0:
            query_params = {"per_page": "100", "page": current_page}
            response = requests.get(url=f"{self._GH_API_URL_ROOT}/orgs/{org_id}/repos",
                                    params=query_params)
            utils.print_trace(f"rest result = ({response.status_code})")

            if not response.ok:
                msg = f"failed retrieving repos for organization '{org_id}' via rest API"
                utils.exit_with_message(msg, 1)

            response_json = response.json()
            if len(response_json) == 0:
                current_page = -1
            else:
                for repo in response_json:
                    repo_name = repo["name"]
                    utils.print_debug(f"getting data for repo {repo_name}")

                    response_repo = requests.get(url=f"{self._GH_API_URL_ROOT}/repos/{org_id}/{repo_name}",
                                                 headers=self._headers)
                    utils.print_trace(f"rest result = ({response_repo.status_code})")

                    if not response_repo.ok:
                        msg = f"failed retrieving data for repo '{repo_name}' of organization '{org_id}' via rest API"
                        utils.exit_with_message(msg, 1)

                    result = response_repo.json()
                    utils.print_trace(json.dumps(result))
                    repos.append(result)

                current_page += 1

        return repos

    def update_repo(self, org_id: str, repo_name: str, data: dict[str, str]) -> None:
        utils.print_debug("updating repo settings via rest API")

        response = requests.patch(url=f"{self._GH_API_URL_ROOT}/repos/{org_id}/{repo_name}",
                                  headers=self._headers,
                                  data=json.dumps(data))
        utils.print_trace(f"rest result = ({response.status_code}, {response.text})")

        if not response.ok:
            utils.exit_with_message(f"failed to update settings for repo '{repo_name}'", 1)

        utils.print_debug(f"updated {len(data)} repo setting(s) via rest api")

    def add_repo(self, org_id: str, data: dict[str, str]) -> None:
        repo_name = data["name"]
        utils.print_debug(f"creating repo '{repo_name}' via rest API")

        response = requests.post(url=f"{self._GH_API_URL_ROOT}/orgs/{org_id}/repos",
                                 headers=self._headers,
                                 data=json.dumps(data))
        utils.print_trace(f"rest result = ({response.status_code}, {response.text})")

        if not response.ok:
            utils.exit_with_message(f"failed to add repo with name '{repo_name}'", 1)

        utils.print_debug(f"added webhook with url '{repo_name}' via rest api")
