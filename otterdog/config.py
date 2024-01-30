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
from typing import Any, Optional

import jq  # type: ignore

from . import credentials
from .credentials import CredentialProvider
from .credentials.bitwarden_provider import BitwardenVault
from .credentials.inmemory_provider import InmemoryVault
from .credentials.pass_provider import PassVault
from .jsonnet import JsonnetConfig


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
        credential_data: dict[str, Any],
        work_dir: str,
        otterdog_config: OtterdogConfig,
    ) -> OrganizationConfig:
        # get the default organization config to retrieve some properties
        org_config = otterdog_config.get_organization_config(project_name)
        config_repo = org_config.config_repo
        base_template = org_config.base_template

        # construct a custom jsonnet config based on the given work_dir
        base_dir = os.path.join(otterdog_config.jsonnet_base_dir, work_dir)

        jsonnet_config = JsonnetConfig(
            github_id,
            base_dir,
            base_template,
            otterdog_config.local_mode,
        )

        return cls(project_name, github_id, config_repo, base_template, jsonnet_config, credential_data)


class OtterdogConfig:
    def __init__(self, config_file: str, local_mode: bool, working_dir: Optional[str] = None):
        if not os.path.exists(config_file):
            raise RuntimeError(f"configuration file '{config_file}' not found")

        self._config_file = os.path.realpath(config_file)
        self._config_dir = os.path.dirname(self._config_file)
        self._credential_providers: dict[str, CredentialProvider] = {}

        self._local_mode = local_mode

        with open(config_file) as f:
            self._configuration = json.load(f)

        self._jsonnet_config = jq.compile(".defaults.jsonnet // {}").input(self._configuration).first()
        self._github_config = jq.compile(".defaults.github // {}").input(self._configuration).first()
        self._default_credential_provider = (
            jq.compile('.defaults.credentials.provider // ""').input(self._configuration).first()
        )

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
            self._organizations_map[org_config.name] = org_config
            self._organizations_map[org_config.github_id] = org_config

    @property
    def config_file(self) -> str:
        return self._config_file

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
        return self._jsonnet_config["base_template"]

    @property
    def organization_configs(self) -> dict[str, OrganizationConfig]:
        return self._organizations_map

    @property
    def organization_names(self) -> list[str]:
        return list(map(lambda config: config.name, self._organizations))

    def get_project_name(self, github_id: str) -> Optional[str]:
        organization = self._organizations_map.get(github_id)
        if organization is not None:
            return organization.name
        else:
            return None

    def get_organization_config(self, organization_name: str) -> OrganizationConfig:
        org_config = self._organizations_map.get(organization_name)
        if org_config is None:
            raise RuntimeError(f"unknown organization with name / github_id '{organization_name}'")
        return org_config

    def _get_credential_provider(self, provider_type: str) -> credentials.CredentialProvider:
        provider = self._credential_providers.get(provider_type)
        if provider is None:
            match provider_type:
                case "bitwarden":
                    api_token_key = (
                        jq.compile('.defaults.bitwarden.api_token_key // "api_token_admin"')
                        .input(self._configuration)
                        .first()
                    )

                    provider = BitwardenVault(api_token_key)
                    self._credential_providers[provider_type] = provider

                case "pass":
                    password_store_dir = (
                        jq.compile('.defaults.pass.password_store_dir // ""').input(self._configuration).first()
                    )

                    username_pattern = (
                        jq.compile('.defaults.pass.username_pattern // ""').input(self._configuration).first()
                    )

                    password_pattern = (
                        jq.compile('.defaults.pass.password_pattern // ""').input(self._configuration).first()
                    )

                    twofa_seed_pattern = (
                        jq.compile('.defaults.pass.twofa_seed_pattern // ""').input(self._configuration).first()
                    )

                    api_token_pattern = (
                        jq.compile('.defaults.pass.api_token_pattern // ""').input(self._configuration).first()
                    )

                    provider = PassVault(
                        password_store_dir, username_pattern, password_pattern, twofa_seed_pattern, api_token_pattern
                    )
                    self._credential_providers[provider_type] = provider

                case "inmemory":
                    provider = InmemoryVault()
                    self._credential_providers[provider_type] = provider

                case _:
                    raise RuntimeError(f"unsupported credential provider '{provider_type}'")

        return provider

    def get_credentials(self, org_config: OrganizationConfig, only_token: bool = False) -> credentials.Credentials:
        provider_type = org_config.credential_data.get("provider")

        if provider_type is None:
            provider_type = self._default_credential_provider

        if not provider_type:
            raise RuntimeError(f"no credential provider configured for organization '{org_config.name}'")

        provider = self._get_credential_provider(provider_type)
        return provider.get_credentials(org_config.name, org_config.credential_data, only_token)

    def get_secret(self, secret_data: str) -> str:
        if secret_data and ":" in secret_data:
            provider_type, data = re.split(":", secret_data)
            provider = self._get_credential_provider(provider_type)
            return provider.get_secret(data)
        else:
            return secret_data

    def __repr__(self):
        return f"OtterdogConfig('{self.config_file}')"

    @classmethod
    def from_file(cls, config_file: str, local_mode: bool):
        return cls(config_file, local_mode)
