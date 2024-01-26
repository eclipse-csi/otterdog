#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
import os
import subprocess
from typing import Any

from .utils import (
    jsonnet_evaluate_snippet,
    parse_template_url,
    print_debug,
    print_trace,
    print_warn,
)


class JsonnetConfig:
    # FIXME: the function names to create resources should not be hard-coded but
    #        rather follow a convention to add new resources more easily.

    create_org = "newOrg"
    create_org_webhook = "newOrgWebhook"
    create_org_secret = "newOrgSecret"
    create_org_variable = "newOrgVariable"
    create_repo = "newRepo"
    extend_repo = "extendRepo"
    create_repo_webhook = "newRepoWebhook"
    create_repo_secret = "newRepoSecret"
    create_repo_variable = "newRepoVariable"
    create_branch_protection_rule = "newBranchProtectionRule"
    create_repo_ruleset = "newRepoRuleset"
    create_environment = "newEnvironment"

    def __init__(self, org_id: str, base_dir: str, base_template_url: str, local_only: bool):
        self._org_id = org_id
        self._base_dir = base_dir

        repo_url, file, ref = parse_template_url(base_template_url)

        self._base_template_repo_url = repo_url
        self._base_template_repo_name = os.path.basename(repo_url)
        self._base_template_file = file
        self._base_template_ref = ref

        self._local_only = local_only

        self._default_org_config: dict[str, Any] | None = None
        self._default_org_webhook_config: dict[str, Any] | None = None
        self._default_org_secret_config: dict[str, Any] | None = None
        self._default_org_variable_config: dict[str, Any] | None = None
        self._default_repo_config: dict[str, Any] | None = None
        self._default_repo_webhook_config: dict[str, Any] | None = None
        self._default_repo_secret_config: dict[str, Any] | None = None
        self._default_repo_variable_config: dict[str, Any] | None = None
        self._default_branch_protection_rule_config: dict[str, Any] | None = None
        self._default_repo_ruleset_config: dict[str, Any] | None = None
        self._default_environment_config: dict[str, Any] | None = None

        self._initialized = False

    @property
    def org_id(self) -> str:
        return self._org_id

    def init_template(self) -> None:
        if self._initialized is True:
            return

        if not self._local_only:
            self._init_base_template()

        template_file = self.template_file
        print_debug(f"loading template file '{template_file}'")
        if not os.path.exists(self.template_file):
            raise RuntimeError(f"template file '{template_file}' does not exist")

        # load the default settings for the organization
        self._default_org_config = self.default_org_config_for_org_id("default")

        try:
            # load the default org webhook config
            org_webhook_snippet = f"(import '{template_file}').{self.create_org_webhook}('default')"
            self._default_org_webhook_config = jsonnet_evaluate_snippet(org_webhook_snippet)
        except RuntimeError:
            print_warn("no default org webhook config found, webhooks will be skipped")
            self._default_org_webhook_config = None

        try:
            # load the default org secret config
            org_secret_snippet = f"(import '{template_file}').{self.create_org_secret}('default')"
            self._default_org_secret_config = jsonnet_evaluate_snippet(org_secret_snippet)
        except RuntimeError:
            print_warn("no default org secret config found, secrets will be skipped")
            self._default_org_secret_config = None

        try:
            # load the default org variable config
            org_variable_snippet = f"(import '{template_file}').{self.create_org_variable}('default')"
            self._default_org_variable_config = jsonnet_evaluate_snippet(org_variable_snippet)
        except RuntimeError:
            print_warn("no default org variable config found, variables will be skipped")
            self._default_org_variable_config = None

        try:
            # load the default repo config
            repo_snippet = f"(import '{template_file}').{self.create_repo}('default')"
            self._default_repo_config = jsonnet_evaluate_snippet(repo_snippet)
        except RuntimeError:
            print_warn("no default repo config found, repos will be skipped")
            self._default_repo_config = None

        try:
            # load the default repo webhook config
            repo_webhook_snippet = f"(import '{template_file}').{self.create_repo_webhook}('default')"
            self._default_repo_webhook_config = jsonnet_evaluate_snippet(repo_webhook_snippet)
        except RuntimeError:
            print_warn("no default repo webhook config found, webhooks will be skipped")
            self._default_repo_webhook_config = None

        try:
            # load the default repo secret config
            repo_secret_snippet = f"(import '{template_file}').{self.create_repo_secret}('default')"
            self._default_repo_secret_config = jsonnet_evaluate_snippet(repo_secret_snippet)
        except RuntimeError:
            print_warn("no default repo secret config found, secrets will be skipped")
            self._default_repo_secret_config = None

        try:
            # load the default repo variable config
            repo_variable_snippet = f"(import '{template_file}').{self.create_repo_variable}('default')"
            self._default_repo_variable_config = jsonnet_evaluate_snippet(repo_variable_snippet)
        except RuntimeError:
            print_warn("no default repo variable config found, variables will be skipped")
            self._default_repo_variable_config = None

        try:
            # load the default branch protection rule config
            branch_protection_snippet = f"(import '{template_file}').{self.create_branch_protection_rule}('default')"
            self._default_branch_protection_rule_config = jsonnet_evaluate_snippet(branch_protection_snippet)
        except RuntimeError:
            print_warn("no default branch protection rule config found, branch protection rules will be skipped")
            self._default_branch_protection_rule_config = None

        try:
            # load the default repo ruleset config
            branch_protection_snippet = f"(import '{template_file}').{self.create_repo_ruleset}('default')"
            self._default_repo_ruleset_config = jsonnet_evaluate_snippet(branch_protection_snippet)
        except RuntimeError:
            print_warn("no default repo ruleset config found, rulesets will be skipped")
            self._default_repo_ruleset_config = None

        try:
            # load the default environment config
            environment_snippet = f"(import '{template_file}').{self.create_environment}('default')"
            self._default_environment_config = jsonnet_evaluate_snippet(environment_snippet)
        except RuntimeError:
            print_warn("no default environment config found, environments will be skipped")
            self._default_environment_config = None

        self._initialized = True

    @property
    def default_org_config(self):
        return self._default_org_config

    def default_org_config_for_org_id(self, org_id: str):
        try:
            # load the default settings for the organization
            snippet = f"(import '{self.template_file}').{self.create_org}('{org_id}')"
            return jsonnet_evaluate_snippet(snippet)
        except RuntimeError as ex:
            raise RuntimeError(f"failed to get default organization config for org '{org_id}': {ex}")

    @property
    def default_org_webhook_config(self):
        return self._default_org_webhook_config

    @property
    def default_org_secret_config(self):
        return self._default_org_secret_config

    @property
    def default_org_variable_config(self):
        return self._default_org_variable_config

    @property
    def default_repo_config(self):
        return self._default_repo_config

    @property
    def default_repo_webhook_config(self):
        return self._default_repo_webhook_config

    @property
    def default_repo_secret_config(self):
        return self._default_repo_secret_config

    @property
    def default_repo_variable_config(self):
        return self._default_repo_variable_config

    @property
    def default_branch_protection_rule_config(self):
        return self._default_branch_protection_rule_config

    @property
    def default_repo_ruleset_config(self):
        return self._default_repo_ruleset_config

    @property
    def default_environment_config(self):
        return self._default_environment_config

    @property
    def template_dir(self) -> str:
        return os.path.join(
            self.org_dir,
            "vendor",
            self._base_template_repo_name,
        )

    @property
    def template_file(self) -> str:
        return os.path.join(
            self.template_dir,
            self._base_template_file,
        )

    @property
    def org_dir(self) -> str:
        return f"{self._base_dir}/{self.org_id}"

    @property
    def org_config_file(self) -> str:
        return f"{self.org_dir}/{self.org_id}.jsonnet"

    @property
    def import_statement(self) -> str:
        return f"import 'vendor/{self._base_template_repo_name}/{self._base_template_file}'"

    @property
    def jsonnet_bundle_file(self) -> str:
        return f"{self.org_dir}/jsonnetfile.json"

    @property
    def jsonnet_bundle_lock_file(self) -> str:
        return f"{self.org_dir}/jsonnetfile.lock.json"

    def _init_base_template(self) -> None:
        # create base directory if it does not exist yet
        if not os.path.exists(self.org_dir):
            os.makedirs(self.org_dir)

        content = {
            "version": 1,
            "dependencies": [
                {
                    "source": {
                        "git": {
                            "remote": f"{self._base_template_repo_url}.git",
                            "subdir": "",
                        }
                    },
                    "version": f"{self._base_template_ref}",
                }
            ],
            "legacyImports": True,
        }

        with open(self.jsonnet_bundle_file, "w") as file:
            file.write(json.dumps(content, indent=2))

        # create an empty lock file if it does not exist yet
        lock_file = self.jsonnet_bundle_lock_file
        if not os.path.exists(lock_file):
            with open(lock_file, "w") as file:
                file.write("")

        print_debug("running jsonnet-bundler update")
        cwd = os.getcwd()

        try:
            os.chdir(self.org_dir)
            status, result = subprocess.getstatusoutput("jb update")
            print_trace(f"result = ({status}, {result})")

            if status != 0:
                raise RuntimeError(result)

        finally:
            os.chdir(cwd)

    def __repr__(self) -> str:
        return f"JsonnetConfig('{self._base_dir}, '{self._base_template_file}')"
