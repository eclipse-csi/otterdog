#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import json
import os
import re
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Protocol

from .credentials.bitwarden_provider import BitwardenVault
from .credentials.inmemory_provider import InMemoryVault
from .credentials.pass_provider import PassVault
from .jsonnet import JsonnetConfig
from .logging import get_logger
from .utils import deep_merge_dict, query_json

if TYPE_CHECKING:
    from otterdog.credentials import CredentialProvider, Credentials

_logger = get_logger(__name__)


class OrganizationConfig:
    def __init__(
        self,
        name: str,
        github_id: str,
        config_repo: str,
        base_template: str,
        jsonnet_config: JsonnetConfig,
        credential_data: dict[str, Any],
    ):
        self._name = name
        self._github_id = github_id
        self._config_repo = config_repo
        self._base_template = base_template
        self._jsonnet_config = jsonnet_config
        self._credential_data = credential_data

    @property
    def name(self):
        return self._name

    @property
    def github_id(self) -> str:
        return self._github_id

    @property
    def config_repo(self) -> str:
        return self._config_repo

    @property
    def base_template(self) -> str:
        return self._base_template

    @property
    def jsonnet_config(self) -> JsonnetConfig:
        return self._jsonnet_config

    @property
    def credential_data(self) -> dict[str, Any]:
        return self._credential_data

    @credential_data.setter
    def credential_data(self, data: dict[str, Any]) -> None:
        self._credential_data = data

    def __repr__(self) -> str:
        return (
            f"OrganizationConfig('{self.name}', '{self.github_id}', "
            f"'{self.config_repo}', {json.dumps(self.credential_data)})"
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], otterdog_config: OtterdogConfig) -> OrganizationConfig:
        name = data.get("name")
        if name is None:
            raise RuntimeError(f"missing required name for organization config with data: '{json.dumps(data)}'")

        github_id = data.get("github_id")
        if github_id is None:
            raise RuntimeError(f"missing required github_id for organization config with name '{name}'")

        config_repo = data.get("config_repo", otterdog_config.default_config_repo)
        base_template = data.get("base_template", otterdog_config.default_base_template)

        jsonnet_config = JsonnetConfig(
            github_id,
            otterdog_config.jsonnet_base_dir,
            base_template,
            otterdog_config.local_mode,
        )

        data = data.get("credentials", {})
        if data is None:
            raise RuntimeError(f"missing required credentials for organization config with name '{name}'")

        return cls(name, github_id, config_repo, base_template, jsonnet_config, data)

    @classmethod
    def of(
        cls,
        project_name: str,
        github_id: str,
        config_repo: str,
        base_template: str,
        credential_data: dict[str, Any],
        base_dir: str,
        work_dir: str,
    ) -> OrganizationConfig:
        jsonnet_config = JsonnetConfig(
            github_id,
            base_dir,
            base_template,
            False,
            work_dir,
        )

        return cls(project_name, github_id, config_repo, base_template, jsonnet_config, credential_data)


class SecretResolver(Protocol):
    @abstractmethod
    def is_supported_secret_provider(self, provider_type: str) -> bool: ...

    @abstractmethod
    def get_secret(self, data: str) -> str: ...


class OtterdogConfig(SecretResolver):
    def __init__(self, config_file: str, local_mode: bool, working_dir: str | None = None):
        if not os.path.exists(config_file):
            raise RuntimeError(f"configuration file '{config_file}' not found")

        self._config_file = os.path.realpath(config_file)
        self._config_dir = os.path.dirname(self._config_file)
        self._credential_providers: dict[str, CredentialProvider] = {}

        self._local_mode = local_mode

        with open(config_file) as f:
            self._configuration = json.load(f)

        if working_dir is None:
            override_defaults_file = os.path.join(self._config_dir, ".otterdog-defaults.json")
            if os.path.exists(override_defaults_file):
                with open(override_defaults_file) as defaults_file:
                    defaults = json.load(defaults_file)
                    _logger.trace("loading default overrides from '%s'", override_defaults_file)
                    self._configuration["defaults"] = deep_merge_dict(
                        defaults, self._configuration.setdefault("defaults")
                    )

        self._jsonnet_config = query_json("defaults.jsonnet", self._configuration) or {}
        self._github_config = query_json("defaults.github", self._configuration) or {}
        self._default_credential_provider = query_json("defaults.credentials.provider", self._configuration) or ""

        if working_dir is None:
            self._jsonnet_base_dir = os.path.join(self._config_dir, self._jsonnet_config.get("config_dir", "orgs"))
        else:
            self._jsonnet_base_dir = os.path.join(working_dir, self._jsonnet_config.get("config_dir", "orgs"))
            if not os.path.exists(self._jsonnet_base_dir):
                os.makedirs(self._jsonnet_base_dir)

        organizations = self._configuration.get("organizations", [])

        self._organizations_map = {}
        self._organizations = []
        for org in organizations:
            org_config = OrganizationConfig.from_dict(org, self)
            self._organizations.append(org_config)
            self._organizations_map[org_config.name.lower()] = org_config
            self._organizations_map[org_config.github_id.lower()] = org_config

    @property
    def config_file(self) -> str:
        return self._config_file

    @property
    def config_dir(self) -> str:
        return self._config_dir

    @property
    def jsonnet_base_dir(self) -> str:
        return self._jsonnet_base_dir

    @property
    def local_mode(self) -> bool:
        return self._local_mode

    @property
    def default_config_repo(self) -> str:
        return self._github_config.get("config_repo", ".otterdog")

    @property
    def default_base_template(self) -> str:
        base_template = self._jsonnet_config.get("base_template")
        if base_template is None:
            raise RuntimeError(
                "need to define a base template in your otterdog config, key: 'defaults.jsonnet.base_template'"
            )
        return base_template

    def _get_organization_config(self, project_or_organization_name: str):
        return self._organizations_map.get(project_or_organization_name.lower())

    @property
    def project_names(self) -> list[str]:
        return [config.name for config in self._organizations]

    @property
    def organization_names(self) -> list[str]:
        return [config.github_id for config in self._organizations]

    def get_project_name(self, github_id: str) -> str | None:
        org_config = self._get_organization_config(github_id)
        if org_config is not None:
            return org_config.name
        else:
            return None

    def get_organization_config(self, project_or_organization_name: str) -> OrganizationConfig:
        org_config = self._get_organization_config(project_or_organization_name)
        if org_config is None:
            raise RuntimeError(f"unknown organization with name / github_id '{project_or_organization_name}'")
        return org_config

    def _get_credential_provider(self, provider_type: str) -> CredentialProvider | None:
        provider = self._credential_providers.get(provider_type)
        if provider is None:
            match provider_type:
                case "bitwarden":
                    api_token_key = (
                        query_json("defaults.bitwarden.api_token_key", self._configuration) or "api_token_admin"
                    )

                    provider = BitwardenVault(api_token_key)
                    self._credential_providers[provider_type] = provider

                case "pass":
                    pass_defaults = query_json("defaults.pass", self._configuration) or {}

                    password_store_dir = pass_defaults.get("password_store_dir", "")
                    username_pattern = pass_defaults.get("username_pattern", "")
                    password_pattern = pass_defaults.get("password_pattern", "")
                    twofa_seed_pattern = pass_defaults.get("twofa_seed_pattern", "")
                    api_token_pattern = pass_defaults.get("api_token_pattern", "")

                    provider = PassVault(
                        password_store_dir, username_pattern, password_pattern, twofa_seed_pattern, api_token_pattern
                    )
                    self._credential_providers[provider_type] = provider

                case "inmemory":
                    provider = InMemoryVault()
                    self._credential_providers[provider_type] = provider

                case _:
                    return None

        return provider

    def get_credentials(self, org_config: OrganizationConfig, only_token: bool = False) -> Credentials:
        provider_type = org_config.credential_data.get("provider")

        if provider_type is None:
            provider_type = self._default_credential_provider

        if not provider_type:
            raise RuntimeError(f"no credential provider configured for organization '{org_config.name}'")

        provider = self._get_credential_provider(provider_type)
        if provider is not None:
            return provider.get_credentials(org_config.name, org_config.credential_data, only_token)
        else:
            raise RuntimeError(f"unsupported credential provider '{provider_type}'")

    def is_supported_secret_provider(self, provider_type: str) -> bool:
        # TODO: make this cleaner
        return provider_type in ["pass", "bitwarden"]

    def get_secret(self, secret_data: str) -> str:
        if secret_data and ":" in secret_data:
            provider_type, data = re.split(":", secret_data)
            provider = self._get_credential_provider(provider_type)
            if provider is not None:
                return provider.get_secret(data)
            else:
                return secret_data
        else:
            return secret_data

    def __repr__(self):
        return f"OtterdogConfig('{self.config_file}')"

    @classmethod
    def from_file(cls, config_file: str, local_mode: bool):
        return cls(config_file, local_mode)
