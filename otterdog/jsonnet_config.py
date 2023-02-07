# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
import os

import _jsonnet

import utils


class JsonnetConfig:
    def __init__(self,
                 data_dir: str,
                 default_config_filename: str = "default.org.jsonnet",
                 import_prefix: str = "../"):

        self.data_dir = data_dir
        self.default_config_filename = default_config_filename
        self.import_prefix = import_prefix

        default_config_file = self.get_default_config_file()
        utils.print_debug(f"loading default configuration file '{default_config_file}'")
        if not os.path.exists(default_config_file):
            msg = f"default configuration file '{self.default_config_filename}' not found in data dir '{data_dir}'"
            utils.exit_with_message(msg, 1)

        try:
            # load the default settings for the organization
            jsonnet_snippet = f"(import '{default_config_file}').newOrg('default')"
            self.default_org_config = json.loads(_jsonnet.evaluate_snippet("snippet", jsonnet_snippet))
        except RuntimeError as ex:
            utils.exit_with_message(f"failed to get default organization config, check default jsonnet config: {ex}", 1)

        try:
            # load the default webhook config
            webhook_snippet = f"(import '{default_config_file}').newWebhook()"
            self.default_org_webhook_config = json.loads(_jsonnet.evaluate_snippet("snippet", webhook_snippet))
        except RuntimeError as ex:
            utils.exit_with_message(f"failed to get default webhook config, check default jsonnet config: {ex}", 1)

        try:
            # load the default repo config
            repo_snippet = f"(import '{default_config_file}').newRepo('default')"
            self.default_org_repo_config = json.loads(_jsonnet.evaluate_snippet("snippet", repo_snippet))
        except RuntimeError as ex:
            utils.exit_with_message(f"failed to get default repo config, check default jsonnet config: {ex}", 1)

        try:
            # load the default branch protection rule config
            repo_snippet = f"(import '{default_config_file}').newBranchProtectionRule('default')"
            self.default_org_branch_config = json.loads(_jsonnet.evaluate_snippet("snippet", repo_snippet))
        except RuntimeError as ex:
            msg = f"failed to get default branch protection rule config, check default jsonnet config: {ex}"
            utils.exit_with_message(msg, 1)

    def get_default_config_file(self) -> str:
        return os.path.join(self.data_dir, self.default_config_filename)

    def get_orgs_config_dir(self) -> str:
        return f"{self.data_dir}/orgs"

    def get_org_config_file(self, org_id: str) -> str:
        return f"{self.get_orgs_config_dir()}/{org_id}.jsonnet"

    def get_import_statement(self) -> str:
        return f"import '{self.import_prefix}{self.default_config_filename}'"
