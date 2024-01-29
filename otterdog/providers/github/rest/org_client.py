#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
import re
from typing import Any

from otterdog.providers.github.exception import GitHubException
from otterdog.utils import print_debug, print_trace, print_warn

from . import RestApi, RestClient, encrypt_value


class OrgClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_settings(self, org_id: str, included_keys: set[str]) -> dict[str, Any]:
        print_debug(f"retrieving settings for org '{org_id}'")

        try:
            settings = await self.requester.async_request_json("GET", f"/orgs/{org_id}")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving settings for organization '{org_id}':\n{ex}").with_traceback(tb)

        if "security_managers" in included_keys:
            security_managers = await self.list_security_managers(org_id)
            settings["security_managers"] = security_managers

        result = {}
        for k, v in settings.items():
            if k in included_keys:
                result[k] = v
                print_trace(f"retrieved setting for '{k}' = '{v}'")

        return result

    async def update_settings(self, org_id: str, data: dict[str, Any]) -> None:
        print_debug(f"updating settings for organization '{org_id}'")

        try:
            await self.requester.async_request_json("PATCH", f"/orgs/{org_id}", data)
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to update settings for organization '{org_id}':\n{ex}").with_traceback(tb)

        if "security_managers" in data:
            await self.update_security_managers(org_id, data["security_managers"])

        print_debug(f"updated {len(data)} setting(s)")

    async def list_security_managers(self, org_id: str) -> list[str]:
        print_debug(f"retrieving security managers for organization {org_id}")

        try:
            result = await self.requester.async_request_json("GET", f"/orgs/{org_id}/security-managers")
            return list(map(lambda x: x["slug"], result))
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(
                f"failed retrieving security managers for organization " f"'{org_id}':\n{ex}"
            ).with_traceback(tb)

    async def update_security_managers(self, org_id: str, security_managers: list[str]) -> None:
        print_debug(f"updating security managers for organization {org_id}")

        current_managers = set(await self.list_security_managers(org_id))

        # first, add all security managers that are not yet configured.
        for team_slug in security_managers:
            if team_slug in current_managers:
                current_managers.remove(team_slug)
            else:
                await self.add_security_manager_team(org_id, team_slug)

        # second, remove the current managers that are left.
        for team_slug in current_managers:
            await self.remove_security_manager_team(org_id, team_slug)

    async def add_security_manager_team(self, org_id: str, team_slug: str) -> None:
        print_debug(f"adding team {team_slug} to security managers for organization {org_id}")

        status, body = await self.requester.async_request_raw(
            "PUT", f"/orgs/{org_id}/security-managers/teams/{team_slug}"
        )

        if status == 204:
            print_debug(f"added team {team_slug} to security managers for organization {org_id}")
        elif status == 404:
            print_warn(
                f"failed to add team '{team_slug}' to security managers for organization {org_id}: " f"team not found"
            )
        else:
            raise RuntimeError(
                f"failed adding team '{team_slug}' to security managers of organization '{org_id}'"
                f"\n{status}: {body}"
            )

    async def remove_security_manager_team(self, org_id: str, team_slug: str) -> None:
        print_debug(f"removing team {team_slug} from security managers for organization {org_id}")

        status, body = await self.requester.async_request_raw(
            "DELETE", f"/orgs/{org_id}/security-managers/teams/{team_slug}"
        )
        if status != 204:
            raise RuntimeError(
                f"failed removing team '{team_slug}' from security managers of organization '{org_id}'"
                f"\n{status}: {body}"
            )

        print_debug(f"removed team {team_slug} from security managers for organization {org_id}")

    async def get_webhooks(self, org_id: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving org webhooks for org '{org_id}'")

        try:
            return await self.requester.async_request_json("GET", f"/orgs/{org_id}/hooks")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving webhooks for org '{org_id}':\n{ex}").with_traceback(tb)

    async def update_webhook(self, org_id: str, webhook_id: int, webhook: dict[str, Any]) -> None:
        print_debug(f"updating org webhook '{webhook_id}' for organization {org_id}")

        try:
            await self.requester.async_request_json("PATCH", f"/orgs/{org_id}/hooks/{webhook_id}", webhook)
            print_debug(f"updated webhook {webhook_id}")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to update org webhook {webhook_id}:\n{ex}").with_traceback(tb)

    async def add_webhook(self, org_id: str, data: dict[str, Any]) -> None:
        url = data["config"]["url"]
        print_debug(f"adding org webhook with url '{url}'")

        # mandatory field "name" = "web"
        data["name"] = "web"

        try:
            await self.requester.async_request_json("POST", f"/orgs/{org_id}/hooks", data)
            print_debug(f"added org webhook with url '{url}'")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to add org webhook with url '{url}':\n{ex}").with_traceback(tb)

    async def delete_webhook(self, org_id: str, webhook_id: int, url: str) -> None:
        print_debug(f"deleting org webhook with url '{url}'")

        status, _ = await self.requester.async_request_raw("DELETE", f"/orgs/{org_id}/hooks/{webhook_id}")

        if status != 204:
            raise RuntimeError(f"failed to delete org webhook with url '{url}'")

        print_debug(f"removed org webhook with url '{url}'")

    async def get_repos(self, org_id: str) -> list[str]:
        print_debug(f"retrieving repos for organization {org_id}")

        params = {"type": "all"}
        try:
            repos = await self.requester.async_request_paged_json("GET", f"/orgs/{org_id}/repos", params)
            return [repo["name"] for repo in repos]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed to retrieve repos for organization '{org_id}':\n{ex}").with_traceback(tb)

    async def get_secrets(self, org_id: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving secrets for org '{org_id}'")

        try:
            response = await self.requester.async_request_json("GET", f"/orgs/{org_id}/actions/secrets")

            secrets = response["secrets"]
            for secret in secrets:
                if secret["visibility"] == "selected":
                    secret["selected_repositories"] = await self._get_selected_repositories_for_secret(
                        org_id, secret["name"]
                    )
            return secrets
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed getting secrets for org '{org_id}':\n{ex}").with_traceback(tb)

    async def _get_selected_repositories_for_secret(self, org_id: str, secret_name: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving selected repositories for secret '{secret_name}'")

        try:
            url = f"/orgs/{org_id}/actions/secrets/{secret_name}/repositories"
            response = await self.requester.async_request_json("GET", url)
            return response["repositories"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving selected repositories:\n{ex}").with_traceback(tb)

    async def _set_selected_repositories_for_secret(
        self, org_id: str, secret_name: str, selected_repository_ids: list[str]
    ) -> None:
        print_debug(f"setting selected repositories for secret '{secret_name}'")

        try:
            data = {"selected_repository_ids": selected_repository_ids}

            url = f"/orgs/{org_id}/actions/secrets/{secret_name}/repositories"
            status, _ = await self.requester.async_request_raw("PUT", url, json.dumps(data))
            if status != 204:
                raise RuntimeError(f"failed to update selected repositories for secret '{secret_name}'")
            else:
                print_debug(f"updated selected repositories for secret '{secret_name}'")

        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving selected repositories:\n{ex}").with_traceback(tb)

    async def update_secret(self, org_id: str, secret_name: str, secret: dict[str, Any]) -> None:
        print_debug(f"updating org secret '{secret_name}'")

        if "name" in secret:
            secret.pop("name")

        if "visibility" in secret:
            visibility = secret["visibility"]
        else:
            visibility = None

        if "selected_repository_ids" in secret:
            selected_repository_ids = secret.pop("selected_repository_ids")
        else:
            selected_repository_ids = None

        await self._encrypt_secret_inplace(org_id, secret)

        status, _ = await self.requester.async_request_raw(
            "PUT", f"/orgs/{org_id}/actions/secrets/{secret_name}", json.dumps(secret)
        )

        if status != 204:
            raise RuntimeError(f"failed to update org secret '{secret_name}'")

        if selected_repository_ids is not None and (visibility is None or visibility == "selected"):
            await self._set_selected_repositories_for_secret(org_id, secret_name, selected_repository_ids)

        print_debug(f"updated org secret '{secret_name}'")

    async def add_secret(self, org_id: str, data: dict[str, str]) -> None:
        secret_name = data.pop("name")
        print_debug(f"adding org secret '{secret_name}'")

        await self._encrypt_secret_inplace(org_id, data)

        status, _ = await self.requester.async_request_raw(
            "PUT", f"/orgs/{org_id}/actions/secrets/{secret_name}", json.dumps(data)
        )

        if status != 201:
            raise RuntimeError(f"failed to add org secret '{secret_name}'")

        print_debug(f"added org secret '{secret_name}'")

    async def _encrypt_secret_inplace(self, org_id: str, data: dict[str, Any]) -> None:
        if "value" in data:
            value = data.pop("value")
            key_id, public_key = await self.get_public_key(org_id)
            data["encrypted_value"] = encrypt_value(public_key, value)
            data["key_id"] = key_id

    async def delete_secret(self, org_id: str, secret_name: str) -> None:
        print_debug(f"deleting org secret '{secret_name}'")

        status, _ = await self.requester.async_request_raw("DELETE", f"/orgs/{org_id}/actions/secrets/{secret_name}")
        if status != 204:
            raise RuntimeError(f"failed to delete org secret '{secret_name}'")

        print_debug(f"removed org secret '{secret_name}'")

    async def get_variables(self, org_id: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving variables for org '{org_id}'")

        try:
            response = await self.requester.async_request_json("GET", f"/orgs/{org_id}/actions/variables")

            secrets = response["variables"]
            for secret in secrets:
                if secret["visibility"] == "selected":
                    secret["selected_repositories"] = await self._get_selected_repositories_for_variable(
                        org_id, secret["name"]
                    )
            return secrets
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed getting variables for org '{org_id}':\n{ex}").with_traceback(tb)

    async def _get_selected_repositories_for_variable(self, org_id: str, variable_name: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving selected repositories for variable '{variable_name}'")

        try:
            url = f"/orgs/{org_id}/actions/variables/{variable_name}/repositories"
            response = await self.requester.async_request_json("GET", url)
            return response["repositories"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving selected repositories:\n{ex}").with_traceback(tb)

    async def _set_selected_repositories_for_variable(
        self, org_id: str, variable_name: str, selected_repository_ids: list[str]
    ) -> None:
        print_debug(f"setting selected repositories for variable '{variable_name}'")

        try:
            data = {"selected_repository_ids": selected_repository_ids}

            url = f"/orgs/{org_id}/actions/variables/{variable_name}/repositories"
            status, _ = await self.requester.async_request_raw("PUT", url, json.dumps(data))
            if status != 204:
                raise RuntimeError(f"failed to update selected repositories for variable '{variable_name}'")

            print_debug(f"updated selected repositories for variable '{variable_name}'")

        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving selected repositories:\n{ex}").with_traceback(tb)

    async def update_variable(self, org_id: str, variable_name: str, variable: dict[str, Any]) -> None:
        print_debug(f"updating org variable '{variable_name}'")

        if "name" in variable:
            variable.pop("name")

        if "visibility" in variable:
            visibility = variable["visibility"]
        else:
            visibility = None

        if "selected_repository_ids" in variable:
            selected_repository_ids = variable.pop("selected_repository_ids")
        else:
            selected_repository_ids = None

        status, body = await self.requester.async_request_raw(
            "PATCH", f"/orgs/{org_id}/actions/variables/{variable_name}", json.dumps(variable)
        )
        if status != 204:
            raise RuntimeError(f"failed to update org variable '{variable_name}': {body}")

        if selected_repository_ids is not None and (visibility is None or visibility == "selected"):
            await self._set_selected_repositories_for_variable(org_id, variable_name, selected_repository_ids)

        print_debug(f"updated org variable '{variable_name}'")

    async def add_variable(self, org_id: str, data: dict[str, str]) -> None:
        variable_name = data.get("name")
        print_debug(f"adding org variable '{variable_name}'")

        status, body = await self.requester.async_request_raw(
            "POST", f"/orgs/{org_id}/actions/variables", json.dumps(data)
        )

        if status != 201:
            raise RuntimeError(f"failed to add org variable '{variable_name}': {body}")

        print_debug(f"added org variable '{variable_name}'")

    async def delete_variable(self, org_id: str, variable_name: str) -> None:
        print_debug(f"deleting org variable '{variable_name}'")

        status, body = await self.requester.async_request_raw(
            "DELETE", f"/orgs/{org_id}/actions/variables/{variable_name}"
        )

        if status != 204:
            raise RuntimeError(f"failed to delete org variable '{variable_name}': {body}")

        print_debug(f"removed org variable '{variable_name}'")

    async def get_public_key(self, org_id: str) -> tuple[str, str]:
        print_debug(f"retrieving org public key for org '{org_id}'")

        try:
            response = await self.requester.async_request_json("GET", f"/orgs/{org_id}/actions/secrets/public-key")
            return response["key_id"], response["key"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving org public key:\n{ex}").with_traceback(tb)

    async def get_team_ids(self, combined_slug: str) -> tuple[int, str]:
        print_debug("retrieving team ids")
        org_id, team_slug = re.split("/", combined_slug)

        try:
            response = await self.requester.async_request_json("GET", f"/orgs/{org_id}/teams/{team_slug}")
            return response["id"], response["node_id"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving team node id:\n{ex}").with_traceback(tb)

    async def get_teams(self, org_id: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving teams for org '{org_id}'")

        try:
            return await self.requester.async_request_json("GET", f"/orgs/{org_id}/teams")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving teams for org '{org_id}':\n{ex}").with_traceback(tb)

    async def get_app_installations(self, org_id: str) -> list[dict[str, Any]]:
        print_debug(f"retrieving app installations for org '{org_id}'")

        try:
            response = await self.requester.async_request_json("GET", f"/orgs/{org_id}/installations")
            return response["installations"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed getting app installations for org '{org_id}':\n{ex}").with_traceback(tb)

    async def get_workflow_settings(self, org_id: str) -> dict[str, Any]:
        print_debug(f"retrieving workflow settings for org '{org_id}'")

        workflow_settings: dict[str, Any] = {}

        try:
            permissions = await self.requester.async_request_json("GET", f"/orgs/{org_id}/actions/permissions")
            workflow_settings.update(permissions)
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving workflow settings for org '{org_id}':\n{ex}").with_traceback(tb)

        if permissions["enabled_repositories"] == "selected":
            workflow_settings["selected_repositories"] = await self._get_selected_repositories_for_workflow_settings(
                org_id
            )
        else:
            workflow_settings["selected_repositories"] = None

        allowed_actions = permissions.get("allowed_actions", "none")
        if allowed_actions == "selected":
            workflow_settings.update(await self._get_selected_actions_for_workflow_settings(org_id))

        if allowed_actions != "none":
            workflow_settings.update(await self._get_default_workflow_permissions(org_id))

        return workflow_settings

    async def update_workflow_settings(self, org_id: str, data: dict[str, Any]) -> None:
        print_debug(f"updating workflow settings for org '{org_id}'")

        permission_data = {k: data[k] for k in ["enabled_repositories", "allowed_actions"] if k in data}
        if len(permission_data) > 0:
            status, body = await self.requester.async_request_raw(
                "PUT", f"/orgs/{org_id}/actions/permissions", json.dumps(permission_data)
            )

            if status != 204:
                raise RuntimeError(f"failed to update workflow settings for org '{org_id}'" f"\n{status}: {body}")

            print_debug(f"updated workflow settings for org '{org_id}'")

        if "selected_repository_ids" in data:
            await self._update_selected_repositories_for_workflow_settings(org_id, data["selected_repository_ids"])

        allowed_action_data = {
            k: data[k] for k in ["github_owned_allowed", "verified_allowed", "patterns_allowed"] if k in data
        }
        if len(allowed_action_data) > 0:
            await self._update_selected_actions_for_workflow_settings(org_id, allowed_action_data)

        default_permission_data = {
            k: data[k] for k in ["default_workflow_permissions", "can_approve_pull_request_reviews"] if k in data
        }
        if len(default_permission_data) > 0:
            await self._update_default_workflow_permissions(org_id, default_permission_data)

        print_debug(f"updated {len(data)} workflow setting(s)")

    async def _get_selected_repositories_for_workflow_settings(self, org_id: str) -> list[dict[str, Any]]:
        print_debug("retrieving selected repositories for org workflow settings")

        try:
            response = await self.requester.async_request_json(
                "GET", f"/orgs/{org_id}/actions/permissions/repositories"
            )
            return response["repositories"]
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving selected repositories:\n{ex}").with_traceback(tb)

    async def _update_selected_repositories_for_workflow_settings(
        self, org_id: str, selected_repository_ids: list[int]
    ) -> None:
        print_debug("updating selected repositories for org workflow settings")

        data = {"selected_repository_ids": selected_repository_ids}
        status, body = await self.requester.async_request_raw(
            "PUT", f"/orgs/{org_id}/actions/permissions/repositories", json.dumps(data)
        )

        if status != 204:
            raise RuntimeError(
                f"failed updating selected repositories for workflow settings of org '{org_id}'" f"\n{status}: {body}"
            )

        print_debug(f"updated selected repositories for workflow settings of org '{org_id}'")

    async def _get_selected_actions_for_workflow_settings(self, org_id: str) -> dict[str, Any]:
        print_debug(f"retrieving allowed actions for org '{org_id}'")

        try:
            return await self.requester.async_request_json(
                "GET", f"/orgs/{org_id}/actions/permissions/selected-actions"
            )
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving allowed actions for org '{org_id}':\n{ex}").with_traceback(tb)

    async def _update_selected_actions_for_workflow_settings(self, org_id: str, data: dict[str, Any]) -> None:
        print_debug(f"updating allowed actions for org '{org_id}'")

        status, body = await self.requester.async_request_raw(
            "PUT", f"/orgs/{org_id}/actions/permissions/selected-actions", json.dumps(data)
        )

        if status != 204:
            raise RuntimeError(f"failed updating allowed actions for org '{org_id}'" f"\n{status}: {body}")

        print_debug(f"updated allowed actions for org '{org_id}'")

    async def _get_default_workflow_permissions(self, org_id: str) -> dict[str, Any]:
        print_debug(f"retrieving default workflow permissions for org '{org_id}'")

        try:
            return await self.requester.async_request_json("GET", f"/orgs/{org_id}/actions/permissions/workflow")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving org default workflow permissions:\n{ex}").with_traceback(tb)

    async def _update_default_workflow_permissions(self, org_id: str, data: dict[str, Any]) -> None:
        print_debug(f"updating default workflow permissions for org '{org_id}'")

        status, body = await self.requester.async_request_raw(
            "PUT", f"/orgs/{org_id}/actions/permissions/workflow", json.dumps(data)
        )

        if status != 204:
            raise RuntimeError(f"failed updating default workflow permissions for org '{org_id}'" f"\n{status}: {body}")

        print_debug(f"updated default workflow permissions for org '{org_id}'")

    async def list_members(self, org_id: str, two_factor_disabled: bool) -> list[dict[str, Any]]:
        print_debug(f"retrieving list of organization members for org '{org_id}'")

        try:
            params = "?filter=2fa_disabled" if two_factor_disabled is True else ""
            return await self.requester.async_request_paged_json("GET", f"/orgs/{org_id}/members{params}")
        except GitHubException as ex:
            tb = ex.__traceback__
            raise RuntimeError(f"failed retrieving org default workflow permissions:\n{ex}").with_traceback(tb)
