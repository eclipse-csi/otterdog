#  *******************************************************************************
#  Copyright (c) 2024-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from typing import Any

from otterdog.logging import get_logger
from otterdog.providers.github.exception import GitHubException
from otterdog.providers.github.rest import RestApi, RestClient, encrypt_value

_logger = get_logger(__name__)


class EnvClient(RestClient):
    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    async def get_secrets(self, org_id: str, repo_name: str, env_name: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving secrets for repo env '%s/%s:%s'", org_id, repo_name, env_name)

        try:
            status, body = await self.requester.request_raw(
                "GET", f"/repos/{org_id}/{repo_name}/environments/{env_name}/secrets"
            )
            if status == 200:
                return json.loads(body)["secrets"]
            else:
                return []
        except GitHubException as ex:
            raise RuntimeError(
                f"failed retrieving secrets for repo env '{org_id}/{repo_name}:{env_name}':\n{ex}"
            ) from ex

    async def update_secret(
        self, org_id: str, repo_name: str, env_name: str, secret_name: str, secret: dict[str, Any]
    ) -> None:
        _logger.debug("updating repo env secret '%s' for repo env '%s/%s:%s'", secret_name, org_id, repo_name, env_name)

        if "name" in secret:
            secret.pop("name")

        await self._encrypt_secret_inplace(org_id, repo_name, env_name, secret)

        status, _ = await self.requester.request_raw(
            "PUT",
            f"/repos/{org_id}/{repo_name}/environments/{env_name}/secrets/{secret_name}",
            json.dumps(secret),
        )

        if status != 204:
            raise RuntimeError(f"failed to update repo env secret '{secret_name}'")

        _logger.debug("updated repo env secret '%s'", secret_name)

    async def add_secret(self, org_id: str, repo_name: str, env_name: str, data: dict[str, str]) -> None:
        secret_name = data.pop("name")
        _logger.debug("adding repo env secret '%s' for repo env '%s/%s:%s'", secret_name, org_id, repo_name, env_name)

        await self._encrypt_secret_inplace(org_id, repo_name, env_name, data)

        status, _ = await self.requester.request_raw(
            "PUT",
            f"/repos/{org_id}/{repo_name}/environments/{env_name}/secrets/{secret_name}",
            json.dumps(data),
        )

        if status != 201:
            raise RuntimeError(f"failed to add repo env secret '{secret_name}'")

        _logger.debug("added repo env secret '%s'", secret_name)

    async def _encrypt_secret_inplace(self, org_id: str, repo_name: str, env_name: str, data: dict[str, Any]) -> None:
        value = data.pop("value")
        key_id, public_key = await self.get_public_key(org_id, repo_name, env_name)
        data["encrypted_value"] = encrypt_value(public_key, value)
        data["key_id"] = key_id

    async def delete_secret(self, org_id: str, repo_name: str, env_name: str, secret_name: str) -> None:
        _logger.debug("deleting repo env secret '%s' for repo env '%s/%s:%s'", secret_name, org_id, repo_name, env_name)

        status, _ = await self.requester.request_raw(
            "DELETE", f"/repos/{org_id}/{repo_name}/environments/{env_name}/secrets/{secret_name}"
        )

        if status != 204:
            raise RuntimeError(f"failed to delete repo env secret '{secret_name}'")

        _logger.debug("removed repo env secret '%s'", secret_name)

    async def get_public_key(self, org_id: str, repo_name: str, env_name: str) -> tuple[str, str]:
        _logger.debug("retrieving repo public key for repo env '%s/%s:%s'", org_id, repo_name, env_name)

        try:
            response = await self.requester.request_json(
                "GET", f"/repos/{org_id}/{repo_name}/environments/{env_name}/secrets/public-key"
            )
            return response["key_id"], response["key"]
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving repo env public key:\n{ex}") from ex

    async def get_variables(self, org_id: str, repo_name: str, env_name: str) -> list[dict[str, Any]]:
        _logger.debug("retrieving variables for repo env '%s/%s:%s'", org_id, repo_name, env_name)

        try:
            status, body = await self.requester.request_raw(
                "GET", f"/repos/{org_id}/{repo_name}/environments/{env_name}/variables"
            )
            if status == 200:
                return json.loads(body)["variables"]
            else:
                return []
        except GitHubException as ex:
            raise RuntimeError(
                f"failed retrieving variables for repo env'{org_id}/{repo_name}:{env_name}':\n{ex}"
            ) from ex

    async def update_variable(
        self, org_id: str, repo_name: str, env_name: str, variable_name: str, variable: dict[str, Any]
    ) -> None:
        _logger.debug("updating repo env variable '%s' for repo '%s/%s:%s'", variable_name, org_id, repo_name, env_name)

        if "name" in variable:
            variable.pop("name")

        status, body = await self.requester.request_raw(
            "PATCH",
            f"/repos/{org_id}/{repo_name}/environments/{env_name}/variables/{variable_name}",
            json.dumps(variable),
        )
        if status != 204:
            raise RuntimeError(f"failed to update repo env variable '{variable_name}': {body}")

        _logger.debug("updated repo env variable '%s'", variable_name)

    async def add_variable(self, org_id: str, repo_name: str, env_name: str, data: dict[str, str]) -> None:
        variable_name = data.get("name")
        _logger.debug(
            "adding repo env variable '%s' for repo env '%s/%s:%s'", variable_name, org_id, repo_name, env_name
        )

        status, body = await self.requester.request_raw(
            "POST",
            f"/repos/{org_id}/{repo_name}/environments/{env_name}/variables",
            json.dumps(data),
        )

        if status != 201:
            raise RuntimeError(f"failed to add repo env variable '{variable_name}': {body}")

        _logger.debug("added repo env variable '%s'", variable_name)

    async def delete_variable(self, org_id: str, repo_name: str, env_name: str, variable_name: str) -> None:
        _logger.debug(
            "deleting repo env variable '%s' for repo env '%s/%s'", variable_name, org_id, repo_name, env_name
        )

        status, _ = await self.requester.request_raw(
            "DELETE", f"/repos/{org_id}/{repo_name}/environments/{env_name}/variables/{variable_name}"
        )

        if status != 204:
            raise RuntimeError(f"failed to delete repo env variable '{variable_name}'")

        _logger.debug("removed repo env variable '%s'", variable_name)
