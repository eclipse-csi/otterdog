#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
import json
import os
import re
from abc import abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING, Any, Protocol

from otterdog.credentials import CredentialProvider

from .jsonnet import JsonnetConfig
from .logging import get_logger
from .utils import deep_merge_dict, query_json

if TYPE_CHECKING:
    from collections.abc import Mapping

    from otterdog.credentials import Credentials

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


class CredentialResolver(SecretResolver):
    def __init__(self, config: OtterdogConfig) -> None:
        self._config = config
        self._credential_providers: dict[str, CredentialProvider] = {}

    def _get_credential_provider(self, provider_type: str) -> CredentialProvider | None:
        provider = self._credential_providers.get(provider_type)
        if provider is None:
            provider = CredentialProvider.create(
                provider_type, query_json(f"defaults.{provider_type}", self._config.configuration) or {}
            )
            if provider is not None:
                self._credential_providers[provider_type] = provider

        return provider

    def get_credentials(self, org_config: OrganizationConfig, only_token: bool = False) -> Credentials:
        provider_type = org_config.credential_data.get("provider")

        if provider_type is None:
            provider_type = self._config.default_credential_provider

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


@dataclasses.dataclass(frozen=True)
class OtterdogConfig:
    configuration: Mapping[str, Any]
    local_mode: bool
    working_dir: str

    _base_url: str = dataclasses.field(init=False)
    _jsonnet_config: Mapping[str, Any] = dataclasses.field(init=False)
    _github_config: Mapping[str, Any] = dataclasses.field(init=False)
    _default_credential_provider: str = dataclasses.field(init=False)
    _jsonnet_base_dir: str = dataclasses.field(init=False)

    _organizations_map: dict[str, OrganizationConfig] = dataclasses.field(init=False, default_factory=dict)
    _organizations: list[OrganizationConfig] = dataclasses.field(init=False, default_factory=list)

    def __post_init__(self):
        object.__setattr__(self, "_base_url", query_json("defaults.base_url", self.configuration) or None)
        object.__setattr__(self, "_jsonnet_config", query_json("defaults.jsonnet", self.configuration) or {})
        object.__setattr__(self, "_github_config", query_json("defaults.github", self.configuration) or {})
        object.__setattr__(
            self, "_default_credential_provider", query_json("defaults.credentials.provider", self.configuration) or ""
        )

        object.__setattr__(
            self,
            "_jsonnet_base_dir",
            os.path.join(self.working_dir, self._jsonnet_config.get("config_dir", "orgs")),
        )
        if not os.path.exists(self._jsonnet_base_dir):
            os.makedirs(self._jsonnet_base_dir)

        organizations = self.configuration.get("organizations", [])
        for org in organizations:
            org_config = OrganizationConfig.from_dict(org, self)
            self._organizations.append(org_config)
            self._organizations_map[org_config.name.lower()] = org_config
            self._organizations_map[org_config.github_id.lower()] = org_config

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def jsonnet_base_dir(self) -> str:
        return self._jsonnet_base_dir

    @property
    def default_config_repo(self) -> str:
        return self._github_config.get("config_repo", ".otterdog")

    @property
    def default_team_exclusions(self) -> list[str]:
        return self._github_config.get("exclude_teams", [])

    @cached_property
    def exclude_teams_pattern(self) -> re.Pattern | None:
        team_exclusions = self.default_team_exclusions
        if len(team_exclusions) == 0:
            return None
        else:
            return re.compile("|".join(team_exclusions))

    @property
    def default_credential_provider(self) -> str:
        return self._default_credential_provider

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

    @classmethod
    def from_file(cls, config_file: str, local_mode: bool, working_dir: str | None = None) -> OtterdogConfig:
        if not os.path.exists(config_file):
            raise RuntimeError(f"configuration file '{config_file}' not found")

        config_file_file = os.path.realpath(config_file)
        config_file_dir = os.path.dirname(config_file)

        with open(config_file_file) as f:
            configuration = json.load(f)

        if working_dir is None:
            override_defaults_file = os.path.join(config_file_dir, ".otterdog-defaults.json")
            if os.path.exists(override_defaults_file):
                with open(override_defaults_file) as defaults_file:
                    defaults = json.load(defaults_file)
                    _logger.trace("loading default overrides from '%s'", override_defaults_file)
                    configuration["defaults"] = deep_merge_dict(defaults, configuration.setdefault("defaults", {}))

        return cls(configuration, local_mode, working_dir if working_dir is not None else config_file_dir)

    @classmethod
    def from_dict(cls, configuration: Mapping[str, Any], local_mode: bool, working_dir: str) -> OtterdogConfig:
        return cls(configuration, local_mode, working_dir)
