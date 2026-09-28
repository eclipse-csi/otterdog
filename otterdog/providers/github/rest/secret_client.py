#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from otterdog.logging import get_logger
from otterdog.providers.github.exception import GitHubException

from . import RestApi, RestClient, encrypt_value

_logger = get_logger(__name__)


class SecretScope(Enum):
    """GitHub secret endpoint families which use the same encrypted-value protocol."""

    ORGANIZATION_ACTIONS = "organization_actions"
    ORGANIZATION_DEPENDABOT = "organization_dependabot"
    ORGANIZATION_CODESPACES = "organization_codespaces"
    REPOSITORY_ACTIONS = "repository_actions"
    REPOSITORY_DEPENDABOT = "repository_dependabot"
    REPOSITORY_CODESPACES = "repository_codespaces"
    ENVIRONMENT = "environment"


class SecretClient(RestClient):
    """Scope-aware client for GitHub's encrypted secret APIs.

    The endpoint families differ only in their URL prefix and whether an
    organization secret exposes repository visibility.  Keeping those details
    here prevents each model/provider method from reimplementing encryption,
    pagination, and selected-repository handling.
    """

    def __init__(self, rest_api: RestApi):
        super().__init__(rest_api)

    @staticmethod
    def _path(
        scope: SecretScope,
        org_id: str,
        repo_name: str | None = None,
        environment_name: str | None = None,
        suffix: str = "",
    ) -> str:
        """Build the endpoint for a scope, including its optional resource suffix."""
        if scope in {
            SecretScope.ORGANIZATION_ACTIONS,
            SecretScope.ORGANIZATION_DEPENDABOT,
            SecretScope.ORGANIZATION_CODESPACES,
        }:
            segment = {
                SecretScope.ORGANIZATION_ACTIONS: "actions",
                SecretScope.ORGANIZATION_DEPENDABOT: "dependabot",
                SecretScope.ORGANIZATION_CODESPACES: "codespaces",
            }[scope]
            return f"/orgs/{org_id}/{segment}/secrets{suffix}"

        if repo_name is None:
            raise ValueError(f"repository name is required for secret scope '{scope.value}'")

        if scope is SecretScope.ENVIRONMENT:
            if environment_name is None:
                raise ValueError("environment name is required for environment secrets")
            return f"/repos/{org_id}/{repo_name}/environments/{environment_name}/secrets{suffix}"

        segment = {
            SecretScope.REPOSITORY_ACTIONS: "actions",
            SecretScope.REPOSITORY_DEPENDABOT: "dependabot",
            SecretScope.REPOSITORY_CODESPACES: "codespaces",
        }[scope]
        return f"/repos/{org_id}/{repo_name}/{segment}/secrets{suffix}"

    @staticmethod
    def _is_organization_scope(scope: SecretScope) -> bool:
        """Return whether a scope supports organization-level visibility metadata."""
        return scope in {
            SecretScope.ORGANIZATION_ACTIONS,
            SecretScope.ORGANIZATION_DEPENDABOT,
            SecretScope.ORGANIZATION_CODESPACES,
        }

    async def get(
        self,
        scope: SecretScope,
        org_id: str,
        repo_name: str | None = None,
        environment_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """List every secret page and expand selected repositories for org scopes.

        ``request_paged_json`` starts with GitHub's maximum page size and follows
        the response ``Link`` header, so callers receive a complete collection.
        Failed reads must propagate: treating unreadable secrets or repository
        selections as empty would let imports discard existing configuration.
        """
        path = self._path(scope, org_id, repo_name, environment_name)
        _logger.debug("retrieving %s secrets from '%s'", scope.value, path)

        try:
            secrets = await self.requester.request_paged_json("GET", path, entries_key="secrets")
            if self._is_organization_scope(scope):
                for secret in secrets:
                    if secret.get("visibility") == "selected":
                        selected_path = self._path(
                            scope,
                            org_id,
                            suffix=f"/{secret['name']}/repositories",
                        )
                        secret["selected_repositories"] = await self.requester.request_paged_json(
                            "GET",
                            selected_path,
                            entries_key="repositories",
                        )
            return secrets
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving {scope.value} secrets from '{path}':\n{ex}") from ex

    async def get_public_key(
        self,
        scope: SecretScope,
        org_id: str,
        repo_name: str | None = None,
        environment_name: str | None = None,
    ) -> tuple[str, str]:
        """Retrieve the public key and key identifier used for encryption."""
        path = self._path(scope, org_id, repo_name, environment_name, "/public-key")
        try:
            response = await self.requester.request_json("GET", path)
            return response["key_id"], response["key"]
        except GitHubException as ex:
            raise RuntimeError(f"failed retrieving the public key for '{path}':\n{ex}") from ex

    async def add(
        self,
        scope: SecretScope,
        org_id: str,
        data: dict[str, Any],
        repo_name: str | None = None,
        environment_name: str | None = None,
    ) -> None:
        """Create a secret after encrypting its value with the scope's public key."""
        secret_name = data.get("name")
        if not isinstance(secret_name, str):
            raise TypeError("secret name is required")

        payload = await self._encrypted_payload(scope, org_id, data, repo_name, environment_name)
        path = self._path(scope, org_id, repo_name, environment_name, f"/{secret_name}")
        status, body = await self.requester.request_raw("PUT", path, json.dumps(payload))
        if status != 201:
            raise RuntimeError(f"failed to add {scope.value} secret '{secret_name}': {body}")

    async def update(
        self,
        scope: SecretScope,
        org_id: str,
        secret_name: str,
        data: dict[str, Any],
        repo_name: str | None = None,
        environment_name: str | None = None,
    ) -> None:
        """Replace an existing secret after encrypting its value when supplied."""
        payload = await self._encrypted_payload(scope, org_id, data, repo_name, environment_name)
        path = self._path(scope, org_id, repo_name, environment_name, f"/{secret_name}")
        status, body = await self.requester.request_raw("PUT", path, json.dumps(payload))
        if status != 204:
            raise RuntimeError(f"failed to update {scope.value} secret '{secret_name}': {body}")

    async def delete(
        self,
        scope: SecretScope,
        org_id: str,
        secret_name: str,
        repo_name: str | None = None,
        environment_name: str | None = None,
    ) -> None:
        """Delete a secret by name without requesting its encrypted value."""
        path = self._path(scope, org_id, repo_name, environment_name, f"/{secret_name}")
        status, body = await self.requester.request_raw("DELETE", path)
        if status != 204:
            raise RuntimeError(f"failed to delete {scope.value} secret '{secret_name}': {body}")

    async def _encrypted_payload(
        self,
        scope: SecretScope,
        org_id: str,
        data: dict[str, Any],
        repo_name: str | None,
        environment_name: str | None,
    ) -> dict[str, Any]:
        """Translate model data into GitHub's encrypted secret request payload."""
        payload = dict(data)
        payload.pop("name", None)

        if "value" in payload:
            secret_value = payload.pop("value")
            key_id, public_key = await self.get_public_key(scope, org_id, repo_name, environment_name)
            payload["encrypted_value"] = encrypt_value(public_key, secret_value)
            payload["key_id"] = key_id

        return payload
