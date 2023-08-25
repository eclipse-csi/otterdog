# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
import re
from typing import Any

from otterdog.utils import print_debug, print_trace, print_warn

from . import RestApi, RestClient, encrypt_value
from ..exception import GitHubException


class OrgClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    def get_org_settings(self, org_id: str, included_keys: set[str]) -> dict[str, Any]:
        print_debug(f"retrieving settings for organization {org_id}")

        try:
            settings = self.requester.request_json("GET", f"/orgs/{org_id}")
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
            self.requester.request_json("PATCH", f"/orgs/{org_id}", data)
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to update settings for organization '{org_id}':\n{ex}").with_traceback(tb)

        if "security_managers" in data:
            self.update_security_managers(org_id, data["security_managers"])

        print_debug(f"updated {len(data)} setting(s)")

    def list_security_managers(self, org_id: str) -> list[str]:
        print_debug(f"retrieving security managers for organization {org_id}")

        try:
            result = self.requester.request_json("GET", f"/orgs/{org_id}/security-managers")
            return list(map(lambda x: x["slug"], result))
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(
                f"failed retrieving security managers for organization " f"'{org_id}':\n{ex}"
            ).with_traceback(tb)

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

        response = self.requester.request_raw("PUT", f"/orgs/{org_id}/security-managers/teams/{team_slug}")

        if response.status_code == 204:
            print_debug(f"added team {team_slug} to security managers for organization {org_id}")
        elif response.status_code == 404:
            print_warn(
                f"failed to add team '{team_slug}' to security managers for organization {org_id}: " f"team not found"
            )
        else:
            raise RuntimeError(
                f"failed adding team '{team_slug}' to security managers of organization '{org_id}'"
                f"\n{response.status_code}: {response.text}"
            )

    def remove_security_manager_team(self, org_id: str, team_slug: str) -> None:
        print_debug(f"removing team {team_slug} from security managers for organization {org_id}")

        response = self.requester.request_raw("DELETE", f"/orgs/{org_id}/security-managers/teams/{team_slug}")
        if response.status_code != 204:
            raise RuntimeError(
                f"failed removing team '{team_slug}' from security managers of organization '{org_id}'"
                f"\n{response.status_code}: {response.text}"
            )
        else:
            print_debug(f"removed team {team_slug} from security managers for organization {org_id}")

    def get_org_webhooks(self, org_id: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving org webhooks for org '{org_id}'")

        try:
            return self.requester.request_json("GET", f"/orgs/{org_id}/hooks")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving webhooks for org '{org_id}':\n{ex}").with_traceback(tb)

    def update_org_webhook(self, org_id: str, webhook_id: int, webhook: dict[str, Any]) -> None:
        print_debug(f"updating org webhook '{webhook_id}' for organization {org_id}")

        try:
            self.requester.request_json("PATCH", f"/orgs/{org_id}/hooks/{webhook_id}", webhook)
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
            self.requester.request_json("POST", f"/orgs/{org_id}/hooks", data)
            print_debug(f"added org webhook with url '{url}'")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to add org webhook with url '{url}':\n{ex}").with_traceback(tb)

    def delete_org_webhook(self, org_id: str, webhook_id: int, url: str) -> None:
        print_debug(f"deleting org webhook with url '{url}'")

        response = self.requester.request_raw("DELETE", f"/orgs/{org_id}/hooks/{webhook_id}")

        if response.status_code != 204:
            raise RuntimeError(f"failed to delete org webhook with url '{url}'")

        print_debug(f"removed org webhook with url '{url}'")

    def get_repos(self, org_id: str) -> list[str]:
        print_debug(f"retrieving repos for organization {org_id}")

        params = {"type": "all"}
        try:
            repos = self.requester.request_paged_json("GET", f"/orgs/{org_id}/repos", params)
            return [repo["name"] for repo in repos]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to retrieve repos for organization '{org_id}':\n{ex}").with_traceback(tb)

    def get_org_secrets(self, org_id: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving secrets for org '{org_id}'")

        try:
            response = self.requester.request_json("GET", f"/orgs/{org_id}/actions/secrets")

            secrets = response["secrets"]
            for secret in secrets:
                if secret["visibility"] == "selected":
                    secret["selected_repositories"] = self._get_selected_repositories_for_org_secret(
                        org_id, secret["name"]
                    )
            return secrets
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed getting secrets for org '{org_id}':\n{ex}").with_traceback(tb)

    def _get_selected_repositories_for_org_secret(self, org_id: str, secret_name: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving selected repositories secret '{secret_name}'")

        try:
            url = f"/orgs/{org_id}/actions/secrets/{secret_name}/repositories"
            response = self.requester.request_json("GET", url)
            return response["repositories"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving selected repositories:\n{ex}").with_traceback(tb)

    def update_org_secret(self, org_id: str, secret_name: str, secret: dict[str, Any]) -> None:
        print_debug(f"updating org secret '{secret_name}'")

        if "name" in secret:
            secret.pop("name")

        self.encrypt_org_secret_inplace(org_id, secret)

        response = self.requester.request_raw(
            "PUT", f"/orgs/{org_id}/actions/secrets/{secret_name}", json.dumps(secret)
        )
        if response.status_code != 204:
            raise RuntimeError(f"failed to update org secret '{secret_name}'")
        else:
            print_debug(f"updated org secret '{secret_name}'")

    def add_org_secret(self, org_id: str, data: dict[str, str]) -> None:
        secret_name = data.pop("name")
        print_debug(f"adding org secret '{secret_name}'")

        self.encrypt_org_secret_inplace(org_id, data)

        response = self.requester.request_raw("PUT", f"/orgs/{org_id}/actions/secrets/{secret_name}", json.dumps(data))
        if response.status_code != 201:
            raise RuntimeError(f"failed to add org secret '{secret_name}'")
        else:
            print_debug(f"added org secret '{secret_name}'")

    def encrypt_org_secret_inplace(self, org_id: str, data: dict[str, Any]) -> None:
        value = data.pop("value")
        key_id, public_key = self.get_org_public_key(org_id)
        data["encrypted_value"] = encrypt_value(public_key, value)
        data["key_id"] = key_id

    def delete_org_secret(self, org_id: str, secret_name: str) -> None:
        print_debug(f"deleting org secret '{secret_name}'")

        response = self.requester.request_raw("DELETE", f"/orgs/{org_id}/actions/secrets/{secret_name}")
        if response.status_code != 204:
            raise RuntimeError(f"failed to delete org secret '{secret_name}'")

        print_debug(f"removed org secret '{secret_name}'")

    def get_org_public_key(self, org_id: str) -> tuple[str, str]:
        print_debug(f"retrieving org public key for org '{org_id}'")

        try:
            response = self.requester.request_json("GET", f"/orgs/{org_id}/actions/secrets/public-key")
            return response["key_id"], response["key"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving org public key:\n{ex}").with_traceback(tb)

    def get_team_ids(self, combined_slug: str) -> tuple[int, str]:
        print_debug("retrieving team ids")
        org_id, team_slug = re.split("/", combined_slug)

        try:
            response = self.requester.request_json("GET", f"/orgs/{org_id}/teams/{team_slug}")
            return response["id"], response["node_id"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving team node id:\n{ex}").with_traceback(tb)

    def get_app_installations(self, org_id: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving app installations for org '{org_id}'")

        try:
            response = self.requester.request_json("GET", f"/orgs/{org_id}/installations")
            return response["installations"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed getting app installations for org '{org_id}':\n{ex}").with_traceback(tb)
