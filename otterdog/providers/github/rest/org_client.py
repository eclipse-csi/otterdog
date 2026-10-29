#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from typing import Any

from otterdog.providers.github.exception import GitHubException, InsufficientPermissionsException
from otterdog.utils import get_logger

from . import RestApi, RestClient

_logger = get_logger(__name__)


class OrgClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_id(self, org_id: str) -> int:
        _logger.debug("retrieving id for org '%s'", org_id)

        try:
            settings = await self.requester.request_json("GET", f"/orgs/{org_id}")
            return settings["id"]
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving id for org '{org_id}':\n{ex}") from ex

    async def is_archived(self, org_id: str) -> bool:
        _logger.debug("checking if org '%s' is archived", org_id)

        try:
            settings = await self.requester.request_json("GET", f"/orgs/{org_id}")
            return settings["archived_at"] is not None
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving archived_at for org '{org_id}':\n{ex}") from ex

    async def get_settings(self, org_id: str, included_keys: set[str]) -> dict[str, Any]:
        _logger.debug("retrieving settings for org '%s'", org_id)

        try:
            settings = await self.requester.request_json("GET", f"/orgs/{org_id}")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving settings for org '{org_id}':\n{ex}") from ex

        if "security_managers" in included_keys:
            security_manager_role_id = await self.get_role_id(org_id, "security_manager")
            # handle gracefully if the role does not exist
            if security_manager_role_id is None:
                settings["security_managers"] = []
            else:
                security_managers = await self.list_security_managers(org_id, str(security_manager_role_id))
                settings["security_managers"] = security_managers

        if "default_code_security_configurations_disabled" in included_keys:
            default_configs = await self._get_default_code_security_configurations(org_id)
            settings["default_code_security_configurations_disabled"] = len(default_configs) == 0

        immutable_releases_keys = {
            "immutable_releases_enforced_repositories",
            "immutable_releases_selected_repositories",
        }
        if len(included_keys.intersection(immutable_releases_keys)) > 0:
            await self._fill_immutable_releases_settings(org_id, settings)

        result = {}
        for k, v in settings.items():
            if k in included_keys:
                result[k] = v
                _logger.trace(f"retrieved setting for '{k}' = '{v}'")

        return result

    async def update_settings(self, org_id: str, data: dict[str, Any]) -> None:
        _logger.debug("updating settings for org '%s'", org_id)
        changes = len(data)

        # settings that are not part of the organization resource, they are updated via dedicated endpoints
        security_managers = data.pop("security_managers", None)
        default_code_security_configuration_disabled = data.pop("default_code_security_configurations_disabled", None)
        immutable_releases_enforced_repositories = data.pop("immutable_releases_enforced_repositories", None)
        immutable_releases_selected_repositories = data.pop("immutable_releases_selected_repositories", None)

        try:
            if len(data) > 0:
                await self.requester.request_json("PATCH", f"/orgs/{org_id}", data)
        except GitHubException as ex:
            raise RuntimeError(f"failed to update settings for org '{org_id}':\n{ex}") from ex

        if security_managers is not None:
            await self.update_security_managers(org_id, security_managers)

        if default_code_security_configuration_disabled is not None:
            if default_code_security_configuration_disabled is True:
                await self._disable_default_code_security_configurations(org_id)
            else:
                _logger.warning("trying to enable default code security configurations")

        if immutable_releases_enforced_repositories is not None:
            immutable_release_data = {"enforced_repositories": immutable_releases_enforced_repositories}

            if immutable_releases_enforced_repositories == "selected":
                immutable_release_data["selected_repository_ids"] = await self.rest_api.repo.get_repo_ids(
                    org_id, immutable_releases_selected_repositories or []
                )

            await self._update_immutable_releases_settings(org_id, immutable_release_data)
        elif immutable_releases_selected_repositories is not None:
            await self._update_selected_repositories_for_immutable_releases(
                org_id,
                await self.rest_api.repo.get_repo_ids(org_id, immutable_releases_selected_repositories),
            )

        _logger.debug("updated %d setting(s)", changes)

    async def _fill_immutable_releases_settings(self, org_id: str, settings: dict[str, Any]) -> None:
        immutable_releases = await self._get_immutable_releases_settings(org_id)
        if immutable_releases is None:
            # leave the settings unset, they will not be taken into account when computing changes
            return

        enforced_repositories = immutable_releases["enforced_repositories"]
        settings["immutable_releases_enforced_repositories"] = enforced_repositories

        if enforced_repositories == "selected":
            settings["immutable_releases_selected_repositories"] = [
                repo["name"] for repo in await self._get_selected_repositories_for_immutable_releases(org_id)
            ]
        else:
            settings["immutable_releases_selected_repositories"] = []

    async def _get_immutable_releases_settings(self, org_id: str) -> dict[str, Any] | None:
        _logger.debug("retrieving immutable release settings for org '%s'", org_id)

        try:
            return await self.requester.request_json("GET", f"/orgs/{org_id}/settings/immutable-releases")
        except (GitHubException, InsufficientPermissionsException) as ex:
            # a 403 caused by missing OAuth scopes is raised as InsufficientPermissionsException
            if ex.status == 404:
                _logger.debug("immutable releases not available for org '%s', treating as disabled", org_id)
                return {"enforced_repositories": "none"}
            if ex.status in (402, 403):
                _logger.warning(
                    "immutable release settings for org '%s' not available (status=%s), "
                    "any configured setting will not be validated",
                    org_id,
                    ex.status,
                )
                return None
            raise RuntimeError(f"failed retrieving immutable release settings for org '{org_id}':\n{ex}") from ex

    async def _update_immutable_releases_settings(self, org_id: str, data: dict[str, Any]) -> None:
        _logger.debug("updating immutable release settings for org '%s'", org_id)

        status, body = await self.requester.request_raw(
            "PUT",
            f"/orgs/{org_id}/settings/immutable-releases",
            json.dumps(data),
        )

        if status != 200:
            raise RuntimeError(f"failed updating immutable release settings for org '{org_id}'\n{status}: {body}")

        _logger.debug("updated immutable release settings for org '%s'", org_id)

    async def _get_selected_repositories_for_immutable_releases(self, org_id: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving selected repositories for immutable release settings of org '%s'", org_id)

        try:
            return await self.requester.request_paged_json(
                "GET", f"/orgs/{org_id}/settings/immutable-releases/repositories", entries_key="repositories"
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving selected repositories for immutable release settings:\n{ex}") from ex

    async def _update_selected_repositories_for_immutable_releases(
        self, org_id: str, selected_repository_ids: list[int]
    ) -> None:
        _logger.debug("updating selected repositories for immutable release settings of org '%s'", org_id)

        status, body = await self.requester.request_raw(
            "PUT",
            f"/orgs/{org_id}/settings/immutable-releases/repositories",
            json.dumps({"selected_repository_ids": selected_repository_ids}),
        )

        if status != 204:
            raise RuntimeError(
                f"failed updating selected repositories for immutable release settings of org '{org_id}'\n"
                f"{status}: {body}"
            )

        _logger.debug("updated selected repositories for immutable release settings of org '%s'", org_id)

    async def list_security_managers(self, org_id: str, role_id: str) -> list[str]:
        _logger.debug("retrieving security managers for org '%s'", org_id)

        try:
            result = await self.requester.request_json("GET", f"/orgs/{org_id}/organization-roles/{role_id}/teams")
            return [x["slug"] for x in result]
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving security managers for org '{org_id}':\n{ex}") from ex

    async def update_security_managers(self, org_id: str, security_managers: list[str]) -> None:
        _logger.debug("updating security managers for org '%s'", org_id)

        security_manager_role_id = await self.get_role_id(org_id, "security_manager")

        if security_manager_role_id is None:
            _logger.warning(
                "failed to update security managers for org '%s' as role '%s' does not exist yet",
                org_id,
                "security_manager",
            )
            return

        current_managers = set(await self.list_security_managers(org_id, str(security_manager_role_id)))

        # first, add all security managers that are not yet configured.
        for team_slug in security_managers:
            if team_slug in current_managers:
                current_managers.remove(team_slug)
            else:
                await self.assign_role_to_team(org_id, str(security_manager_role_id), team_slug)

        # second, remove the current managers that are left.
        for team_slug in current_managers:
            await self.remove_role_from_team(org_id, str(security_manager_role_id), team_slug)

    async def assign_role_to_team(self, org_id: str, role_id: str, team_slug: str) -> None:
        _logger.debug("assigning role with id '%s' to team '%s' for org '%s'", role_id, team_slug, org_id)

        status, body = await self.requester.request_raw(
            "PUT", f"/orgs/{org_id}/organization-roles/teams/{team_slug}/{role_id}"
        )

        if status == 204:
            _logger.debug("assigned role '%s' to team '%s' for org '%s'", role_id, team_slug, org_id)
        elif status == 404:
            _logger.warning(
                "failed to assign role '%s' to team '%s' for org '%s': %s",
                role_id,
                team_slug,
                org_id,
                body,
            )
        else:
            raise RuntimeError(
                f"failed assigning role '{role_id}' to team '{team_slug}' in org '{org_id}'\n{status}: {body}"
            )

    async def remove_role_from_team(self, org_id: str, role_id: str, team_slug: str) -> None:
        _logger.debug("removing role '%s' from team '%s' in org '%s'", role_id, team_slug, org_id)

        status, body = await self.requester.request_raw(
            "DELETE", f"/orgs/{org_id}/organization-roles/teams/{team_slug}/{role_id}"
        )
        if status != 204:
            raise RuntimeError(
                f"failed removing role '{role_id}' from team '{team_slug}' in org '{org_id}'\n{status}: {body}"
            )

        _logger.debug("removed role '%s' from team '%s' in org '%s'", role_id, team_slug, org_id)

    async def get_role_id(self, org_id: str, role_name: str) -> int | None:
        _logger.debug("retrieving id for role with name '%s' in org '%s'", role_name, org_id)

        try:
            result = await self.requester.request_json("GET", f"/orgs/{org_id}/organization-roles")
            for role in result["roles"]:
                if role["name"] == role_name:
                    return role["id"]

            return None
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving custom roles for org '{org_id}':\n{ex}") from ex

    async def get_custom_roles(self, org_id: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving custom roles for org '%s'", org_id)

        try:
            result = await self.requester.request_json("GET", f"/orgs/{org_id}/organization-roles")
            return [r for r in result["roles"] if r["source"] != "Predefined"]
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving custom roles for org '{org_id}':\n{ex}") from ex

    async def update_custom_role(self, org_id: str, role_id: int, role_name: str, role: dict[str, Any]) -> None:
        _logger.debug("updating org role with name '%s' for org '%s'", role_name, org_id)

        try:
            await self.requester.request_json("PATCH", f"/orgs/{org_id}/organization-roles/{role_id}", role)
            _logger.debug("updated org role with name '%s'", role_name)
        except GitHubException as ex:
            raise RuntimeError(f"failed to update org role '{role_name}':\n{ex}") from ex

    async def add_custom_role(self, org_id: str, role_name: str, data: dict[str, Any]) -> None:
        _logger.debug("adding org role with name '%s' for org '%s'", role_name, org_id)

        try:
            await self.requester.request_json("POST", f"/orgs/{org_id}/organization-roles", data)
            _logger.debug("added org role with name '%s'", role_name)
        except GitHubException as ex:
            raise RuntimeError(f"failed to add org role with name '{role_name}':\n{ex}") from ex

    async def delete_custom_role(self, org_id: str, role_id: int, role_name: str) -> None:
        _logger.debug("deleting org role with name '%s' for org '%s'", role_name, org_id)

        status, _ = await self.requester.request_raw("DELETE", f"/orgs/{org_id}/organization-roles/{role_id}")

        if status != 204:
            raise RuntimeError(f"failed to delete org role with name '{role_name}'")

        _logger.debug("removed org role with name '%s'", role_name)

    async def get_code_security_configurations(self, org_id: str) -> list[dict[str, Any]]:
        """
        Returns all code security configurations available to the organization, including the predefined
        configurations (e.g. GitHub recommended) and configurations of the enterprise, see 'target_type'.
        """
        _logger.debug("retrieving code security configurations for org '%s'", org_id)

        try:
            configurations = await self.requester.request_paged_json(
                "GET", f"/orgs/{org_id}/code-security/configurations"
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving code security configurations for org '{org_id}':\n{ex}") from ex

        # the defaults for new repositories are retrieved separately, include them in the configuration
        defaults_by_id = {
            config["configuration"]["id"]: config["default_for_new_repos"]
            for config in await self._get_default_code_security_configurations(org_id)
            if "configuration" in config
        }

        for configuration in configurations:
            configuration["default_for_new_repos"] = defaults_by_id.get(configuration["id"], "none")

        return configurations

    async def get_code_security_configuration_id(self, org_id: str, name: str) -> int | None:
        _logger.debug("retrieving id for code security configuration with name '%s' in org '%s'", name, org_id)

        try:
            configurations = await self.requester.request_paged_json(
                "GET", f"/orgs/{org_id}/code-security/configurations"
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving code security configurations for org '{org_id}':\n{ex}") from ex

        # only configurations of the organization itself can be managed
        for configuration in configurations:
            if configuration.get("target_type") == "organization" and configuration["name"] == name:
                return configuration["id"]

        return None

    async def add_code_security_configuration(self, org_id: str, data: dict[str, Any]) -> int:
        name = data.get("name", "<unknown>")
        _logger.debug("adding code security configuration with name '%s' for org '%s'", name, org_id)

        try:
            response = await self.requester.request_json("POST", f"/orgs/{org_id}/code-security/configurations", data)
            _logger.debug("added code security configuration with name '%s'", name)
            return response["id"]
        except GitHubException as ex:
            raise RuntimeError(f"failed to add code security configuration with name '{name}':\n{ex}") from ex

    async def update_code_security_configuration(
        self, org_id: str, configuration_id: int, name: str, data: dict[str, Any]
    ) -> None:
        _logger.debug("updating code security configuration with name '%s' for org '%s'", name, org_id)

        # GitHub responds with 204 if the update did not change the configuration
        status, body = await self.requester.request_raw(
            "PATCH", f"/orgs/{org_id}/code-security/configurations/{configuration_id}", json.dumps(data)
        )

        if status not in (200, 204):
            raise RuntimeError(f"failed to update code security configuration with name '{name}':\n{body}")

        _logger.debug("updated code security configuration with name '%s'", name)

    async def update_code_security_configuration_default(
        self, org_id: str, configuration_id: int, name: str, default_for_new_repos: str
    ) -> None:
        _logger.debug(
            "setting code security configuration with name '%s' as default for '%s' new repos in org '%s'",
            name,
            default_for_new_repos,
            org_id,
        )

        try:
            await self.requester.request_json(
                "PUT",
                f"/orgs/{org_id}/code-security/configurations/{configuration_id}/defaults",
                {"default_for_new_repos": default_for_new_repos},
            )
        except GitHubException as ex:
            raise RuntimeError(
                f"failed to set default for new repos of code security configuration with name '{name}':\n{ex}"
            ) from ex

    async def delete_code_security_configuration(self, org_id: str, configuration_id: int, name: str) -> None:
        _logger.debug("deleting code security configuration with name '%s' for org '%s'", name, org_id)

        status, _ = await self.requester.request_raw(
            "DELETE", f"/orgs/{org_id}/code-security/configurations/{configuration_id}"
        )

        if status != 204:
            raise RuntimeError(f"failed to delete code security configuration with name '{name}'")

        _logger.debug("removed code security configuration with name '%s'", name)

    async def get_code_security_configuration_repositories(self, org_id: str, configuration_id: int) -> list[str]:
        _logger.debug(
            "retrieving repositories of code security configuration '%d' in org '%s'", configuration_id, org_id
        )

        # detached or removed repositories are not associated with the configuration anymore,
        # repositories for which the attachment failed are reported as not being attached
        params = {"status": "attached,attaching,updating,enforced"}

        try:
            result = await self.requester.request_paged_json(
                "GET", f"/orgs/{org_id}/code-security/configurations/{configuration_id}/repositories", params=params
            )
            return [entry["repository"]["name"] for entry in result]
        except GitHubException as ex:
            raise RuntimeError(
                f"failed retrieving repositories of code security configuration '{configuration_id}':\n{ex}"
            ) from ex

    async def attach_code_security_configuration_by_name(self, org_id: str, name: str, repo_names: list[str]) -> None:
        """
        Attaches the code security configuration with the given name to the given repositories,
        and waits until the attachment completed, as the settings it sets are applied asynchronously.
        """
        configuration_id = await self.get_code_security_configuration_id(org_id, name)
        if configuration_id is None:
            raise RuntimeError(f"failed to find code security configuration with name '{name}' in org '{org_id}'")

        repo_ids = await self.rest_api.repo.get_repo_ids(org_id, repo_names)
        await self.attach_code_security_configuration(org_id, configuration_id, name, repo_ids)

        for repo_name in repo_names:
            await self.rest_api.repo.wait_for_code_security_configuration(org_id, repo_name, configuration_id)

    async def attach_code_security_configuration(
        self, org_id: str, configuration_id: int, name: str, repository_ids: list[int]
    ) -> None:
        _logger.debug("attaching code security configuration with name '%s' to repositories %s", name, repository_ids)

        data = {"scope": "selected", "selected_repository_ids": repository_ids}
        status, body = await self.requester.request_raw(
            "POST", f"/orgs/{org_id}/code-security/configurations/{configuration_id}/attach", json.dumps(data)
        )

        if status not in (200, 202):
            raise RuntimeError(f"failed to attach code security configuration with name '{name}':\n{body}")

        _logger.debug("attached code security configuration with name '%s'", name)

    async def get_custom_properties(self, org_id: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving custom properties for org '%s'", org_id)

        try:
            return await self.requester.request_json("GET", f"/orgs/{org_id}/properties/schema")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving custom properties for org '{org_id}':\n{ex}") from ex

    async def add_custom_property(self, org_id: str, property_name: str, data: dict[str, Any]) -> None:
        _logger.debug("adding org custom property with name '%s' for org '%s'", property_name, org_id)

        try:
            await self.requester.request_json("PUT", f"/orgs/{org_id}/properties/schema/{property_name}", data)
            _logger.debug("added org custom property with name '%s'", property_name)
        except GitHubException as ex:
            raise RuntimeError(f"failed to add org custom property with name '{property_name}':\n{ex}") from ex

    async def update_custom_property(self, org_id: str, property_name: str, data: dict[str, Any]) -> None:
        _logger.debug(f"updating org custom property with name '{property_name}'")

        try:
            await self.requester.request_json("PUT", f"/orgs/{org_id}/properties/schema/{property_name}", data)
            _logger.debug("updated org custom property with name '%s'", property_name)
        except GitHubException as ex:
            raise RuntimeError(f"failed to update org custom property with name '{property_name}':\n{ex}") from ex

    async def delete_custom_property(self, org_id: str, property_name: str) -> None:
        _logger.debug("deleting org custom property with name '%s'", property_name)

        status, _ = await self.requester.request_raw("DELETE", f"/orgs/{org_id}/properties/schema/{property_name}")

        if status != 204:
            raise RuntimeError(f"failed to delete org custom property with name '{property_name}'")

        _logger.debug("removed org custom property with name '%s'", property_name)

    async def get_webhook_id(self, org_id: str, url: str) -> str:
        _logger.debug("retrieving id for org webhook with url '%s' for org '%s'", url, org_id)

        webhooks = await self.get_webhooks(org_id)

        has_wildcard_url = url.endswith("*")
        stripped_url = url.rstrip("*")

        for webhook in webhooks:
            webhook_url = webhook["config"]["url"]
            if (has_wildcard_url is True and webhook_url.startswith(stripped_url)) or webhook_url == url:
                return webhook["id"]

        raise RuntimeError(f"failed to find org webhook with url '{url}'")

    async def get_webhooks(self, org_id: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving org webhooks for org '%s'", org_id)

        try:
            return await self.requester.request_json("GET", f"/orgs/{org_id}/hooks")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving webhooks for org '{org_id}':\n{ex}") from ex

    async def update_webhook(self, org_id: str, webhook_id: int, webhook: dict[str, Any]) -> None:
        _logger.debug("updating org webhook '%d' for org '%s'", webhook_id, org_id)

        try:
            await self.requester.request_json("PATCH", f"/orgs/{org_id}/hooks/{webhook_id}", webhook)
            _logger.debug("updated webhook %d", webhook_id)
        except GitHubException as ex:
            raise RuntimeError(f"failed to update org webhook {webhook_id}:\n{ex}") from ex

    async def add_webhook(self, org_id: str, data: dict[str, Any]) -> None:
        url = data["config"]["url"]
        _logger.debug("adding org webhook with url '%s' for org '%s'", url, org_id)

        # mandatory field "name" = "web"
        data["name"] = "web"

        try:
            await self.requester.request_json("POST", f"/orgs/{org_id}/hooks", data)
            _logger.debug("added org webhook with url '%s'", url)
        except GitHubException as ex:
            raise RuntimeError(f"failed to add org webhook with url '{url}':\n{ex}") from ex

    async def delete_webhook(self, org_id: str, webhook_id: int, url: str) -> None:
        _logger.debug("deleting org webhook with url '%s' for org '%s'", url, org_id)

        status, _ = await self.requester.request_raw("DELETE", f"/orgs/{org_id}/hooks/{webhook_id}")

        if status != 204:
            raise RuntimeError(f"failed to delete org webhook with url '{url}'")

        _logger.debug("removed org webhook with url '%s'", url)

    async def get_repos(self, org_id: str) -> list[str]:
        _logger.debug("retrieving repos for org '%s'", org_id)

        params = {"type": "all"}
        try:
            repos = await self.requester.request_paged_json("GET", f"/orgs/{org_id}/repos", params=params)
            return [repo["name"] for repo in repos]
        except GitHubException as ex:
            raise RuntimeError(f"failed to retrieve repos for org '{org_id}':\n{ex}") from ex

    async def get_variables(self, org_id: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving variables for org '%s'", org_id)

        try:
            response = await self.requester.request_json("GET", f"/orgs/{org_id}/actions/variables")

            secrets = response["variables"]
            for secret in secrets:
                if secret["visibility"] == "selected":
                    secret["selected_repositories"] = await self._get_selected_repositories_for_variable(
                        org_id, secret["name"]
                    )
            return secrets
        except GitHubException as ex:
            raise RuntimeError(f"failed getting variables for org '{org_id}':\n{ex}") from ex

    async def _get_selected_repositories_for_variable(self, org_id: str, variable_name: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving selected repositories for variable '%s' in org '%s'", variable_name, org_id)

        try:
            url = f"/orgs/{org_id}/actions/variables/{variable_name}/repositories"
            response = await self.requester.request_json("GET", url)
            return response["repositories"]
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving selected repositories:\n{ex}") from ex

    async def _set_selected_repositories_for_variable(
        self, org_id: str, variable_name: str, selected_repository_ids: list[str]
    ) -> None:
        _logger.debug("setting selected repositories for variable '%s' in org '%s'", variable_name, org_id)

        try:
            data = {"selected_repository_ids": selected_repository_ids}

            url = f"/orgs/{org_id}/actions/variables/{variable_name}/repositories"
            status, _ = await self.requester.request_raw("PUT", url, json.dumps(data))
            if status != 204:
                raise RuntimeError(f"failed to update selected repositories for variable '{variable_name}'")

            _logger.debug("updated selected repositories for variable '%s'", variable_name)

        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving selected repositories:\n{ex}") from ex

    async def update_variable(self, org_id: str, variable_name: str, variable: dict[str, Any]) -> None:
        _logger.debug("updating org variable '%s' in org '%s'", variable_name, org_id)

        if "name" in variable:
            variable.pop("name")

        visibility = variable.get("visibility")

        if "selected_repository_ids" in variable:
            selected_repository_ids = variable.pop("selected_repository_ids")
        else:
            selected_repository_ids = None

        status, body = await self.requester.request_raw(
            "PATCH", f"/orgs/{org_id}/actions/variables/{variable_name}", json.dumps(variable)
        )
        if status != 204:
            raise RuntimeError(f"failed to update org variable '{variable_name}': {body}")

        if selected_repository_ids is not None and (visibility is None or visibility == "selected"):
            await self._set_selected_repositories_for_variable(org_id, variable_name, selected_repository_ids)

        _logger.debug("updated org variable '%s'", variable_name)

    async def add_variable(self, org_id: str, data: dict[str, str]) -> None:
        variable_name = data.get("name")
        _logger.debug("adding org variable '%s' in org '%s'", variable_name, org_id)

        status, body = await self.requester.request_raw("POST", f"/orgs/{org_id}/actions/variables", json.dumps(data))

        if status != 201:
            raise RuntimeError(f"failed to add org variable '{variable_name}': {body}")

        _logger.debug("added org variable '%s'", variable_name)

    async def delete_variable(self, org_id: str, variable_name: str) -> None:
        _logger.debug("deleting org variable '%s' in org '%s'", variable_name, org_id)

        status, body = await self.requester.request_raw("DELETE", f"/orgs/{org_id}/actions/variables/{variable_name}")

        if status != 204:
            raise RuntimeError(f"failed to delete org variable '{variable_name}': {body}")

        _logger.debug("removed org variable '%s'", variable_name)

    async def get_app_installations(self, org_id: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving app installations for org '%s'", org_id)

        try:
            response = await self.requester.request_json("GET", f"/orgs/{org_id}/installations")
            return response["installations"]
        except GitHubException as ex:
            raise RuntimeError(f"failed getting app installations for org '{org_id}':\n{ex}") from ex

    async def get_workflow_settings(self, org_id: str, included_keys: set[str] | None = None) -> dict[str, Any]:
        _logger.debug("retrieving workflow settings for org '%s'", org_id)

        workflow_settings: dict[str, Any] = {}

        try:
            permissions = await self.requester.request_json("GET", f"/orgs/{org_id}/actions/permissions")
            workflow_settings.update(permissions)
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving workflow settings for org '{org_id}':\n{ex}") from ex

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

        workflow_settings.update(await self._get_fork_pr_approval_policy(org_id))

        if included_keys is None or "max_cache_size_gb" in included_keys:
            workflow_settings.update(await self._get_max_cache_size_gb(org_id))

        return workflow_settings

    async def update_workflow_settings(self, org_id: str, data: dict[str, Any]) -> None:
        _logger.debug("updating workflow settings for org '%s'", org_id)

        permission_data = {k: data[k] for k in ["enabled_repositories", "allowed_actions"] if k in data}
        if len(permission_data) > 0:
            status, body = await self.requester.request_raw(
                "PUT", f"/orgs/{org_id}/actions/permissions", json.dumps(permission_data)
            )

            if status != 204:
                raise RuntimeError(f"failed to update workflow settings for org '{org_id}'\n{status}: {body}")

            _logger.debug("updated workflow settings for org '%s'", org_id)

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

        if "approval_policy" in data:
            await self._update_fork_pr_approval_policy(org_id, {"approval_policy": data["approval_policy"]})

        if "max_cache_size_gb" in data:
            await self._update_max_cache_size_gb(org_id, data["max_cache_size_gb"])

        _logger.debug("updated %d workflow setting(s)", len(data))

    async def _get_max_cache_size_gb(self, org_id: str) -> dict[str, Any]:
        _logger.debug("retrieving cache size for org '%s'", org_id)

        response = await self._get_optional_json(
            f"/orgs/{org_id}/actions/cache/storage-limit",
            feature_description=f"cache size for org '{org_id}'",
        )
        if response is None:
            return {}

        if "max_cache_size_gb" not in response:
            # An incomplete success response must not become an absent setting:
            # reconciliation would then skip drift detection for the configured limit.
            raise RuntimeError(
                f"GitHub response for organization cache size of '{org_id}' does not contain 'max_cache_size_gb'"
            )

        return {"max_cache_size_gb": response["max_cache_size_gb"]}

    async def _update_max_cache_size_gb(self, org_id: str, max_cache_size_gb: int) -> None:
        _logger.debug("updating cache size for org '%s'", org_id)

        status, body = await self.requester.request_raw(
            "PUT",
            f"/orgs/{org_id}/actions/cache/storage-limit",
            data=json.dumps({"max_cache_size_gb": max_cache_size_gb}),
        )

        if status != 204:
            raise RuntimeError(f"failed to update cache size for org '{org_id}': {body}")

        _logger.debug("updated cache size for org '%s'", org_id)

    async def _get_selected_repositories_for_workflow_settings(self, org_id: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving selected repositories for org workflow settings of org '%s'", org_id)

        try:
            response = await self.requester.request_json("GET", f"/orgs/{org_id}/actions/permissions/repositories")
            return response["repositories"]
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving selected repositories:\n{ex}") from ex

    async def _update_selected_repositories_for_workflow_settings(
        self, org_id: str, selected_repository_ids: list[int]
    ) -> None:
        _logger.debug("updating selected repositories for org workflow settings of org '%s'", org_id)

        data = {"selected_repository_ids": selected_repository_ids}
        status, body = await self.requester.request_raw(
            "PUT", f"/orgs/{org_id}/actions/permissions/repositories", json.dumps(data)
        )

        if status != 204:
            raise RuntimeError(
                f"failed updating selected repositories for workflow settings of org '{org_id}'\n{status}: {body}"
            )

        _logger.debug("updated selected repositories for workflow settings of org '%s'", org_id)

    async def _get_selected_actions_for_workflow_settings(self, org_id: str) -> dict[str, Any]:
        _logger.debug("retrieving allowed actions for org '%s'", org_id)

        try:
            return await self.requester.request_json("GET", f"/orgs/{org_id}/actions/permissions/selected-actions")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving allowed actions for org '{org_id}':\n{ex}") from ex

    async def _update_selected_actions_for_workflow_settings(self, org_id: str, data: dict[str, Any]) -> None:
        _logger.debug("updating allowed actions for org '%s'", org_id)

        status, body = await self.requester.request_raw(
            "PUT", f"/orgs/{org_id}/actions/permissions/selected-actions", json.dumps(data)
        )

        if status != 204:
            raise RuntimeError(f"failed updating allowed actions for org '{org_id}'\n{status}: {body}")

        _logger.debug("updated allowed actions for org '%s'", org_id)

    async def _get_default_workflow_permissions(self, org_id: str) -> dict[str, Any]:
        _logger.debug("retrieving default workflow permissions for org '%s'", org_id)

        try:
            return await self.requester.request_json("GET", f"/orgs/{org_id}/actions/permissions/workflow")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving org default workflow permissions:\n{ex}") from ex

    async def _update_default_workflow_permissions(self, org_id: str, data: dict[str, Any]) -> None:
        _logger.debug("updating default workflow permissions for org '%s'", org_id)

        status, body = await self.requester.request_raw(
            "PUT", f"/orgs/{org_id}/actions/permissions/workflow", json.dumps(data)
        )

        if status != 204:
            raise RuntimeError(f"failed updating default workflow permissions for org '{org_id}'\n{status}: {body}")

        _logger.debug("updated default workflow permissions for org '%s'", org_id)

    async def _get_fork_pr_approval_policy(self, org_id: str) -> dict[str, Any]:
        _logger.debug("retrieving fork PR approval policy for org '%s'", org_id)

        try:
            return await self.requester.request_json(
                "GET", f"/orgs/{org_id}/actions/permissions/fork-pr-contributor-approval"
            )
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving fork PR approval policy for org '{org_id}':\n{ex}") from ex

    async def _update_fork_pr_approval_policy(self, org_id: str, data: dict[str, Any]) -> None:
        _logger.debug("updating fork PR approval policy for org '%s'", org_id)

        status, body = await self.requester.request_raw(
            "PUT", f"/orgs/{org_id}/actions/permissions/fork-pr-contributor-approval", json.dumps(data)
        )

        if status != 204:
            raise RuntimeError(f"failed updating fork PR approval policy for org '{org_id}'\n{status}: {body}")

        _logger.debug("updated fork PR approval policy for org '%s'", org_id)

    async def _get_default_code_security_configurations(self, org_id: str) -> list[dict[str, Any]]:
        _logger.debug(f"retrieving default code security configurations for org '{org_id}'")

        try:
            url = f"/orgs/{org_id}/code-security/configurations/defaults"
            return await self.requester.request_json("GET", url)
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving default code security configurations:\n{ex}") from ex

    async def _disable_default_code_security_configurations(self, org_id: str) -> None:
        _logger.debug("retrieving default code security configurations for org '%s'", org_id)

        current_default_configs = await self._get_default_code_security_configurations(org_id)

        for config in current_default_configs:
            configuration_id = config["configuration"]["id"]

            try:
                data = {"default_for_new_repos": "none"}
                url = f"/orgs/{org_id}/code-security/configurations/{configuration_id}/defaults"
                await self.requester.request_json("PUT", url, data=data)
            except GitHubException as ex:
                raise RuntimeError(
                    f"failed disabling default code security configuration with id {configuration_id}:\n{ex}"
                ) from ex

    async def list_members(self, org_id: str, two_factor_disabled: bool = False) -> list[dict[str, Any]]:
        _logger.debug("retrieving list of org members for org '%s'", org_id)

        try:
            params = {"filter": "2fa_disabled"} if two_factor_disabled is True else None
            return await self.requester.request_paged_json("GET", f"/orgs/{org_id}/members", params=params)
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving members:\n{ex}") from ex

    async def get_security_advisories(self, org_id: str, state: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving security advisories for org '%s' with state '%s'", org_id, state)

        try:
            params = {"state": state} if state is not None else None
            return await self.requester.request_paged_json("GET", f"/orgs/{org_id}/security-advisories", params=params)
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving security advisories for org '{org_id}':\n{ex}") from ex

    async def get_rulesets(self, org_id: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving org rulesets for org '%s'", org_id)

        try:
            result = []
            response = await self.requester.request_paged_json("GET", f"/orgs/{org_id}/rulesets")
            for ruleset in response:
                result.append(await self.get_ruleset(org_id, str(ruleset["id"])))
            return result
        except GitHubException as ex:
            if ex.status in (403, 404):
                # org rulesets require a paid plan;
                _logger.debug(
                    "org rulesets not available for org '%s' (status=%s)",
                    org_id,
                    ex.status,
                )
                return []
            raise RuntimeError(f"failed retrieving org rulesets for org '{org_id}':\n{ex}") from ex

    async def get_ruleset(self, org_id: str, ruleset_id: str) -> dict[str, Any]:
        _logger.debug("retrieving org ruleset '%s' for org '%s'", ruleset_id, org_id)

        try:
            return await self.requester.request_json("GET", f"/orgs/{org_id}/rulesets/{ruleset_id}")
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving org ruleset for org '{org_id}':\n{ex}") from ex

    async def get_ruleset_id(self, org_id: str, name: str) -> str:
        _logger.debug("retrieving id for org ruleset with name '%s' for org '%s'", name, org_id)

        rulesets = await self.get_rulesets(org_id)

        for ruleset in rulesets:
            if ruleset["name"] == name:
                return ruleset["id"]

        raise RuntimeError(f"failed to find org ruleset with name '{name}'")

    async def update_ruleset(self, org_id: str, ruleset_id: int, ruleset: dict[str, Any]) -> None:
        _logger.debug("updating org ruleset '%d' for org '%s'", ruleset_id, org_id)

        try:
            await self.requester.request_json("PUT", f"/orgs/{org_id}/rulesets/{ruleset_id}", ruleset)
            _logger.debug("updated org ruleset '%d'", ruleset_id)
        except GitHubException as ex:
            raise RuntimeError(f"failed to update org ruleset {ruleset_id}:\n{ex}") from ex

    async def add_ruleset(self, org_id: str, data: dict[str, Any]) -> None:
        name = data["name"]
        _logger.debug("adding org ruleset with name '%s' for org '%s'", name, org_id)

        try:
            await self.requester.request_json("POST", f"/orgs/{org_id}/rulesets", data)
            _logger.debug(f"added org ruleset with name '{name}'")
        except GitHubException as ex:
            raise RuntimeError(f"failed to add org ruleset with name '{name}':\n{ex}") from ex

    async def delete_ruleset(self, org_id: str, ruleset_id: int, name: str) -> None:
        _logger.debug("deleting org ruleset with name '%s' for org '%s'", name, org_id)

        status, _ = await self.requester.request_raw("DELETE", f"/orgs/{org_id}/rulesets/{ruleset_id}")

        if status != 204:
            raise RuntimeError(f"failed to delete org ruleset with name '{name}'")

        _logger.debug("removed org ruleset with name '%s'", name)
