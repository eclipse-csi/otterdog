#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

import os
from abc import abstractmethod
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from functools import partial
from typing import Any

from colorama import Style

from otterdog import mapping
from otterdog import organization as org
from otterdog.config import OtterdogConfig, OrganizationConfig
from otterdog.providers.github import Github
from otterdog.utils import IndentingPrinter, associate_by_key, print_warn

from . import Operation
from .validate_operation import ValidateOperation


class DiffStatus:
    def __init__(self):
        self.additions = 0
        self.differences = 0
        self.extras = 0

    def total_changes(self) -> int:
        return self.additions + self.differences


class DiffOperation(Operation):
    _DEFAULT_POOL_SIZE = 12

    def __init__(self):
        self.config = None
        self.jsonnet_config = None
        self.gh_client = None
        self._printer = None
        self._validator = ValidateOperation()

    @property
    def printer(self) -> IndentingPrinter:
        return self._printer

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        self.config = config
        self.jsonnet_config = self.config.jsonnet_config
        self._printer = printer
        self._validator.init(config, printer)

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id

        self.printer.print(f"Organization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")
        self.printer.level_up()

        try:
            return self._generate_diff(org_config)
        finally:
            self.printer.level_down()

    def setup_github_client(self, org_config: OrganizationConfig) -> int:
        try:
            credentials = self.config.get_credentials(org_config)
        except RuntimeError as e:
            self.printer.print_error(f"invalid credentials\n{str(e)}")
            return 1

        self.gh_client = Github(credentials)
        return 0

    def verbose_output(self):
        return True

    def resolve_secrets(self) -> bool:
        return True

    def _generate_diff(self, org_config: OrganizationConfig) -> int:
        result = self.setup_github_client(org_config)
        if result != 0:
            return result

        github_id = org_config.github_id
        org_file_name = self.jsonnet_config.get_org_config_file(github_id)

        if not os.path.exists(org_file_name):
            self.printer.print_warn(f"configuration file '{org_file_name}' does not yet exist, run fetch first")
            return 1

        try:
            expected_org = org.load_from_file(github_id, org_file_name, self.config, self.resolve_secrets())
        except RuntimeError as e:
            self.printer.print_error(f"failed to load configuration\n{str(e)}")
            return 1

        # We validate the configuration first and only calculate a plan if
        # there are no validation errors.
        validation_errors = self._validator.validate(expected_org)
        if validation_errors > 0:
            self.printer.print("Planning aborted due to validation errors.")
            return validation_errors

        diff_status = DiffStatus()

        modified_org_settings = self._process_settings(github_id, expected_org, diff_status)
        self._process_webhooks(github_id, expected_org, diff_status)
        self._process_repositories(github_id, expected_org, modified_org_settings, diff_status)

        self.handle_finish(github_id, diff_status)
        return 0

    def _process_settings(self,
                          github_id: str,
                          expected_org: org.Organization,
                          diff_status: DiffStatus) -> dict[str, Any]:
        expected_settings = expected_org.get_settings()

        start = datetime.now()
        if self.verbose_output():
            self.printer.print(f"organization settings: Reading...")

        # filter out web settings if --no-web-ui is used
        expected_settings_keys = expected_settings.keys()
        if self.config.no_web_ui:
            expected_settings_keys = {x for x in expected_settings_keys if not self.gh_client.is_web_org_setting(x)}

        # determine differences for settings.
        current_otterdog_org_settings = self.get_current_org_settings(github_id, expected_settings_keys)

        if self.verbose_output():
            end = datetime.now()
            self.printer.print(f"organization settings: Read complete after {(end - start).total_seconds()}s")

        modified_settings = {}
        for key, expected_value in sorted(expected_settings.items()):
            if key not in expected_settings_keys:
                continue

            if key not in current_otterdog_org_settings:
                self.printer.print_warn(f"unexpected key '{key}' found in configuration, skipping")
                continue

            current_value = current_otterdog_org_settings.get(key)

            if current_value != expected_value:
                modified_settings[key] = (expected_value, current_value)

        if len(modified_settings) > 0:
            # some settings might be read-only, collect the correct number of changes
            # to be executed based on the operations to be performed.
            differences = self.handle_modified_settings(github_id, modified_settings, expected_settings)
            diff_status.differences += differences

        return modified_settings

    def get_current_org_settings(self, github_id: str, settings_keys: set[str]) -> dict[str, Any]:
        # determine differences for settings.
        current_github_org_settings = self.gh_client.get_org_settings(github_id, settings_keys)
        return mapping.map_github_org_settings_data_to_otterdog(current_github_org_settings)

    def _process_webhooks(self, github_id: str, expected_org: org.Organization, diff_status: DiffStatus) -> None:
        start = datetime.now()
        if self.verbose_output():
            self.printer.print(f"\nwebhooks: Reading...")

        expected_webhooks_by_url = associate_by_key(expected_org.get_webhooks(), lambda x: x["url"])
        current_webhooks = self.get_current_webhooks(github_id)

        if self.verbose_output():
            end = datetime.now()
            self.printer.print(f"webhooks: Read complete after {(end - start).total_seconds()}s")

        for webhook_id, current_otterdog_webhook in current_webhooks:
            webhook_url = current_otterdog_webhook["url"]
            expected_webhook = expected_webhooks_by_url.get(webhook_url)
            if expected_webhook is None:
                self.handle_extra_webhook(github_id, current_otterdog_webhook)
                diff_status.extras += 1
                continue

            modified_webhook = {}
            for key, expected_value in expected_webhook.items():
                current_value = current_otterdog_webhook.get(key)

                if key == "secret":
                    if not ((expected_value is not None and current_value is None) or
                            (expected_value is None and current_value is not None)):
                        continue

                if expected_value != current_value:
                    modified_webhook[key] = (expected_value, current_value)
                    diff_status.differences += 1

            if len(modified_webhook) > 0:
                self.handle_modified_webhook(github_id, webhook_id, webhook_url, modified_webhook, expected_webhook)

            expected_webhooks_by_url.pop(webhook_url)

        for webhook_url, webhook in expected_webhooks_by_url.items():
            self.handle_new_webhook(github_id, webhook)
            diff_status.additions += 1

    def get_current_webhooks(self, github_id: str) -> list[tuple[str, dict[str, Any]]]:
        github_webhooks = self.gh_client.get_webhooks(github_id)

        result = []
        for github_webhook in github_webhooks:
            webhook_id = str(github_webhook["id"])
            current_otterdog_webhook = mapping.map_github_org_webhook_data_to_otterdog(github_webhook)
            result.append((webhook_id, current_otterdog_webhook))

        return result

    def _process_repositories(self,
                              github_id: str,
                              expected_org: org.Organization,
                              modified_org_settings: dict[str, Any],
                              diff_status: DiffStatus) -> None:
        start = datetime.now()
        if self.verbose_output():
            self.printer.print(f"\nrepositories: Reading...")

        expected_repos_by_name = associate_by_key(expected_org.get_repos(), lambda x: x["name"])
        current_repos = self.get_current_repos(github_id)

        if self.verbose_output():
            end = datetime.now()
            self.printer.print(f"repositories: Read complete after {(end - start).total_seconds()}s")

        for current_repo_id, current_otterdog_repo_data, current_branch_protection_rules in current_repos:
            current_repo_name = current_otterdog_repo_data["name"]
            is_private = current_otterdog_repo_data["private"]
            is_archived = current_otterdog_repo_data["archived"]

            expected_repo = expected_repos_by_name.get(current_repo_name)

            if expected_repo is None:
                self.handle_extra_repo(github_id, current_otterdog_repo_data)
                diff_status.extras += 1
                continue

            modified_repo = {}
            for key, expected_value in expected_repo.items():
                # branch protection rules are treated separately.
                if key == "branch_protection_rules":
                    continue

                if not mapping.shall_repo_key_be_included(key, is_private, is_archived):
                    continue

                current_value = current_otterdog_repo_data.get(key)
                # special handling for some keys that can be set organization wide
                if key == "web_commit_signoff_required":
                    if key in modified_org_settings:
                        org_value, _ = modified_org_settings.get(key)
                        current_value = org_value

                if expected_value != current_value:
                    diff_status.differences += 1
                    modified_repo[key] = (expected_value, current_value)

            if len(modified_repo) > 0:
                self.handle_modified_repo(github_id, current_repo_name, modified_repo)

            self._process_branch_protection_rules(github_id,
                                                  current_repo_name,
                                                  current_repo_id,
                                                  current_branch_protection_rules,
                                                  expected_repo,
                                                  diff_status)

            expected_repos_by_name.pop(current_repo_name)

        for repo_name, repo in expected_repos_by_name.items():
            new_repo = repo.copy()
            branch_protection_rules = new_repo.pop("branch_protection_rules")
            self.handle_new_repo(github_id, new_repo)

            diff_status.additions += 1

            if len(branch_protection_rules) > 0:
                self._process_branch_protection_rules(github_id, repo_name, "", [], repo, diff_status)

    def _process_single_repo(self, github_id: str, repo_name: str) -> (str, dict[str, Any]):
        repo_data = \
            self.gh_client.get_repo_data(github_id, repo_name)
        repo_data["branch_protection_rules"] = \
            self.gh_client.get_branch_protection_rules(github_id, repo_name)
        return repo_name, repo_data

    def get_current_repos(self, github_id: str) -> list[(str, dict[str, Any], list[(str, dict[str, Any])])]:
        current_repos = self.gh_client.get_repos(github_id)

        # retrieve repo_data and branch_protection_rules in parallel using a pool.
        current_github_repos = {}
        # partially apply the github_id to get a function that only takes one parameter
        process_repo = partial(self._process_single_repo, github_id)
        # use a process pool executor: tests show that this is faster than a ThreadPoolExecutor
        # due to the global interpreter lock.
        with ProcessPoolExecutor() as pool:
            data = pool.map(process_repo, current_repos)
            for (repo_name, repo_data) in data:
                current_github_repos[repo_name] = repo_data

        result = []

        for repo_name, current_github_repo_data in current_github_repos.items():
            current_repo_id = current_github_repo_data["node_id"]

            current_github_rules = current_github_repo_data.pop("branch_protection_rules")

            otterdog_rules = []
            for current_github_rule in current_github_rules:
                rule_id = current_github_rule["id"]

                current_otterdog_rule = \
                    mapping.map_github_branch_protection_rule_data_to_otterdog(current_github_rule)

                otterdog_rules.append((rule_id, current_otterdog_rule))

            current_otterdog_repo_data = mapping.map_github_repo_data_to_otterdog(current_github_repo_data)
            result.append((current_repo_id, current_otterdog_repo_data, otterdog_rules))

        return result

    def _process_branch_protection_rules(self,
                                         org_id: str,
                                         repo_name: str,
                                         repo_id: str,
                                         current_otterdog_rules: list[(str, dict[str, Any])],
                                         expected_repo: dict[str, Any],
                                         diff_status: DiffStatus) -> None:

        expected_branch_protection_rules_by_pattern = \
            associate_by_key(expected_repo.get("branch_protection_rules"), lambda x: x["pattern"])

        is_archived = expected_repo["archived"]
        if is_archived:
            if len(expected_branch_protection_rules_by_pattern) > 0:
                if self.verbose_output():
                    print_warn(f"branch_protection_rules specified for archived project, will be ignored.")
            return

        # only retrieve current rules if the repo_id is available, otherwise it's a new repo
        if repo_id:
            for rule_id, current_otterdog_rule in current_otterdog_rules:
                rule_pattern = current_otterdog_rule["pattern"]

                expected_rule = expected_branch_protection_rules_by_pattern.get(rule_pattern)
                if expected_rule is None:
                    self.handle_extra_rule(org_id, repo_name, repo_id, current_otterdog_rule)
                    diff_status.extras += 1
                    continue

                modified_rule = {}
                for key, expected_value in expected_rule.items():
                    current_value = current_otterdog_rule.get(key)
                    if expected_value != current_value:
                        diff_status.differences += 1
                        modified_rule[key] = (expected_value, current_value)

                if len(modified_rule) > 0:
                    self.handle_modified_rule(org_id, repo_name, rule_pattern, rule_id, modified_rule)

                expected_branch_protection_rules_by_pattern.pop(rule_pattern)

        for rule_pattern, rule in expected_branch_protection_rules_by_pattern.items():
            self.handle_new_rule(org_id, repo_name, repo_id, rule)
            diff_status.additions += 1

    @abstractmethod
    def handle_modified_settings(self,
                                 org_id: str,
                                 modified_settings: dict[str, (Any, Any)],
                                 full_settings: dict[str, Any]) -> int:
        raise NotImplementedError

    @abstractmethod
    def handle_modified_webhook(self,
                                org_id: str,
                                webhook_id: str,
                                webhook_url: str,
                                modified_webhook: dict[str, (Any, Any)],
                                webhook: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_extra_webhook(self, org_id: str, webhook: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_new_webhook(self, org_id: str, data: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_modified_repo(self,
                             org_id: str,
                             repo_name: str,
                             modified_repo: dict[str, (Any, Any)]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_extra_repo(self, org_id: str, repo: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_new_repo(self, org_id: str, data: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_modified_rule(self,
                             org_id: str,
                             repo_name: str,
                             rule_pattern: str,
                             rule_id: str,
                             data: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_extra_rule(self, org_id: str, repo_name: str, repo_id: str, data: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_new_rule(self, org_id: str, repo_name: str, repo_id: str, data: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_finish(self, org_id: str, diff_status: DiffStatus) -> None:
        raise NotImplementedError
