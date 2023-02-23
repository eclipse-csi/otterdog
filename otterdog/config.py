# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
import os
import subprocess
from typing import Any

import jq
import _jsonnet

import bitwarden
import utils
import credentials

_DEFAULT_TEMPLATE_FILE = "default-org.libsonnet"


class JsonnetConfig:
    def __init__(self,
                 data_dir: str,
                 settings: dict[str, Any],
                 import_prefix: str = "../"):

        self._data_dir = data_dir
        self._orgs_dir = jq.compile(f'.config_dir // "orgs"').input(settings).first()

        self._use_jsonnet_bundler = False
        base_template = settings.get("base_template")
        if base_template is None:
            self._base_template_file = _DEFAULT_TEMPLATE_FILE
        else:
            repo = base_template.get("repo")
            if repo is not None:
                self._base_template_repo_url = repo.strip("/")
                self._base_template_repo_name = os.path.basename(self._base_template_repo_url)
                self._base_template_branch = jq.compile(f'.branch // "main"').input(base_template).first()
                self._use_jsonnet_bundler = True

            self._base_template_file = \
                jq.compile(f'.file // "{_DEFAULT_TEMPLATE_FILE}"')\
                  .input(base_template).first()

        self._init_base_template()

        self._import_prefix = import_prefix

        self.create_org = \
            jq.compile(f'.create_org // "newOrg"').input(settings).first()
        self.create_webhook = \
            jq.compile(f'.create_webhook // "newWebhook"').input(settings).first()
        self.create_repo = \
            jq.compile(f'.create_repo // "newRepo"').input(settings).first()
        self.create_branch_protection_rule =\
            jq.compile(f'.create_branch_protection_rule // "newBranchProtectionRule"').input(settings).first()

        template_file = self.template_file
        utils.print_debug(f"loading template file '{template_file}'")
        if not os.path.exists(self.template_file):
            raise RuntimeError(f"template file '{template_file}' does not exist")

        try:
            # load the default settings for the organization
            jsonnet_snippet = f"(import '{template_file}').newOrg('default')"
            self.default_org_config = json.loads(_jsonnet.evaluate_snippet("snippet", jsonnet_snippet))
        except RuntimeError as ex:
            raise RuntimeError(f"failed to get default organization config: {ex}")

        try:
            # load the default webhook config
            webhook_snippet = f"(import '{template_file}').newWebhook()"
            self.default_org_webhook_config = json.loads(_jsonnet.evaluate_snippet("snippet", webhook_snippet))
        except RuntimeError as ex:
            raise RuntimeError(f"failed to get default webhook config: {ex}")

        try:
            # load the default repo config
            repo_snippet = f"(import '{template_file}').newRepo('default')"
            self.default_org_repo_config = json.loads(_jsonnet.evaluate_snippet("snippet", repo_snippet))
        except RuntimeError as ex:
            raise RuntimeError(f"failed to get default repo config: {ex}")

        try:
            # load the default branch protection rule config
            repo_snippet = f"(import '{template_file}').newBranchProtectionRule('default')"
            self.default_org_branch_config = json.loads(_jsonnet.evaluate_snippet("snippet", repo_snippet))
        except RuntimeError as ex:
            raise RuntimeError(f"failed to get default branch protection rule config: {ex}")

    @property
    def template_file(self) -> str:
        if self._use_jsonnet_bundler:
            return os.path.join(self._data_dir,
                                self.orgs_dir,
                                "vendor",
                                self._base_template_repo_name,
                                self._base_template_file)
        else:
            return os.path.join(self._data_dir, self._base_template_file)

    @property
    def orgs_dir(self) -> str:
        return f"{self._data_dir}/{self._orgs_dir}"

    def get_org_config_file(self, org_id: str) -> str:
        return f"{self.orgs_dir}/{org_id}.jsonnet"

    def get_import_statement(self) -> str:
        if self._use_jsonnet_bundler:
            return f"import 'vendor/{self._base_template_repo_name}/{self._base_template_file}'"
        else:
            return f"import '{self._import_prefix}{self._base_template_file}'"

    def get_jsonnet_bundle_file(self) -> str:
        return f"{self.orgs_dir}/jsonnetfile.json"

    def _init_base_template(self) -> None:
        if self._use_jsonnet_bundler:
            content =\
                {
                    "version": 1,
                    "dependencies": [
                        {
                            "source": {
                                "git": {
                                    "remote": f"{self._base_template_repo_url}.git",
                                    "subdir": ""
                                }
                            },
                            "version": f"{self._base_template_branch}"
                        }
                    ],
                    "legacyImports": True
                }

            with open(self.get_jsonnet_bundle_file(), "w") as file:
                file.write(json.dumps(content, indent=2))

            utils.print_debug("running jsonnet-bundler update")
            cwd = os.getcwd()

            try:
                os.chdir(self.orgs_dir)
                status, result = subprocess.getstatusoutput("jb update")
                utils.print_trace(f"result = ({status}, {result})")

                if status != 0:
                    raise RuntimeError()

            finally:
                os.chdir(cwd)

    def __repr__(self) -> str:
        return f"JsonnetConfig('{self._data_dir},'{self._base_template_file}')"


class OrganizationConfig:
    def __init__(self, name, github_id, credential_data):
        self._name = name
        self._github_id = github_id
        self._credential_data = credential_data

    @property
    def name(self):
        return self._name

    @property
    def github_id(self):
        return self._github_id

    @property
    def credential_data(self):
        return self._credential_data

    def __repr__(self) -> str:
        return f"OrganizationConfig('{self.name}', '{self.github_id}', {json.dumps(self._credential_data)})"

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        name = jq.compile(".name").input(data).first()
        if name is None:
            raise RuntimeError(f"missing required name for organization config with data: '{json.dumps(data)}'")

        github_id = jq.compile(".github_id").input(data).first()
        if github_id is None:
            raise RuntimeError(f"missing required github_id for organization config with name '{name}'")

        data = jq.compile(".credentials").input(data).first()
        if data is None:
            raise RuntimeError(f"missing required credentials for organization config with name '{name}'")

        return cls(name, github_id, data)


class OtterdogConfig:
    def __init__(self, config_file: str, force_processing: bool):
        if not os.path.exists(config_file):
            raise RuntimeError(f"configuration file '{config_file}' not found")

        self._config_file = os.path.realpath(config_file)
        self._data_dir = os.path.dirname(self._config_file)
        self._credential_providers = {}
        self._force_processing = force_processing

        with open(config_file) as f:
            self._configuration = json.load(f)

        jsonnet_settings = jq.compile(".defaults.jsonnet // {}").input(self._configuration).first()
        self._jsonnet_config = JsonnetConfig(self.data_dir, jsonnet_settings)

        self._github_config = jq.compile(".defaults.github // {}").input(self._configuration).first()

        organizations = jq.compile(".organizations // []").input(self._configuration).first()
        self._organizations = {}
        for org in organizations:
            org_config = OrganizationConfig.from_dict(org)
            self._organizations[org_config.name] = org_config

    @property
    def config_file(self) -> str:
        return self._config_file

    @property
    def force_processing(self) -> bool:
        return self._force_processing

    @property
    def data_dir(self) -> str:
        return self._data_dir

    @property
    def jsonnet_config(self) -> JsonnetConfig:
        return self._jsonnet_config

    @property
    def config_repo(self) -> str:
        return self._github_config.get("config_repo", "meta-data")

    @property
    def organization_configs(self) -> dict[str, OrganizationConfig]:
        return self._organizations

    def organization_config(self, organization_name: str) -> OrganizationConfig:
        org_config = self._organizations.get(organization_name)
        if org_config is None:
            raise RuntimeError(f"unknown organization with name '{organization_name}'")
        return org_config

    def _get_credential_provider(self, provider_type: str) -> credentials.CredentialProvider:
        provider = self._credential_providers.get(provider_type)
        if provider is None:
            match provider_type:
                case "bitwarden":
                    api_token_key =\
                        jq.compile('.defaults.bitwarden.api_token_key // "api_token_admin"')\
                          .input(self._configuration)\
                          .first()

                    provider = bitwarden.BitwardenVault(api_token_key)
                    self._credential_providers[provider_type] = provider

                case _:
                    raise RuntimeError(f"unsupported credential provider '{provider_type}'")

        return provider

    def get_credentials(self, org_config: OrganizationConfig) -> credentials.Credentials:
        provider_type = org_config.credential_data.get("provider")
        if provider_type is None:
            raise RuntimeError(f"no credential provider configured for organization '{org_config.name}'")

        provider = self._get_credential_provider(provider_type)
        return provider.get_credentials(org_config.credential_data)

    def __repr__(self):
        return f"OtterdogConfig('{self.data_dir}')"

    @classmethod
    def from_file(cls, config_file: str, force_processing: bool):
        return cls(config_file, force_processing)
