# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os
from abc import abstractmethod
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from functools import partial
from typing import Any

from colorama import Style

from . import mapping
from . import organization as org
from . import schemas
from .config import OtterdogConfig, OrganizationConfig
from .github import Github
from .operation import Operation
from .utils import IndentingPrinter, associate_by_key, print_warn
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

    def _generate_diff(self, org_config: OrganizationConfig) -> int:
        try:
            credentials = self.config.get_credentials(org_config)
        except RuntimeError as e:
            self.printer.print_error(f"invalid credentials\n{str(e)}")
            return 1

        self.gh_client = Github(credentials)

        github_id = org_config.github_id
        org_file_name = self.jsonnet_config.get_org_config_file(github_id)

        if not os.path.exists(org_file_name):
            self.printer.print_warn(f"configuration file '{org_file_name}' does not yet exist, run fetch first")
            return 1

        try:
            expected_org = org.load_from_file(github_id,
                                              self.jsonnet_config.get_org_config_file(github_id),
                                              self.config)
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

        self._process_settings(github_id, expected_org, diff_status)
        self._process_webhooks(github_id, expected_org, diff_status)
        self._process_repositories(github_id, expected_org, diff_status)

        self.handle_finish(github_id, diff_status)
        return diff_status.total_changes()

    def _process_settings(self, github_id: str, expected_org: org.Organization, diff_status: DiffStatus) -> None:
        expected_settings = expected_org.get_settings()

        start = datetime.now()
        self.printer.print(f"organization settings: Reading...")

        # determine differences for settings.
        current_github_org_settings = self.gh_client.get_org_settings(github_id, expected_settings.keys())
        current_otterdog_org_settings = mapping.map_github_org_settings_data_to_otterdog(current_github_org_settings)

        end = datetime.now()
        self.printer.print(f"organization settings: Read complete after {(end - start).total_seconds()}s")

        modified_settings = {}
        for key, expected_value in sorted(expected_settings.items()):
            if key not in current_otterdog_org_settings:
                self.printer.print_warn(f"unexpected key '{key}' found in configuration, skipping")
                continue

            current_value = current_otterdog_org_settings.get(key)

            if current_value != expected_value:
                modified_settings[key] = (expected_value, current_value)

        if len(modified_settings) > 0:
            # some settings might be read-only, collect the correct number of changes
            # to be executed based on the operation to be performed.
            differences = self.handle_modified_settings(github_id, modified_settings)
            diff_status.differences += differences

    def _process_webhooks(self, github_id: str, expected_org: org.Organization, diff_status: DiffStatus) -> None:
        start = datetime.now()
        self.printer.print(f"\nwebhooks: Reading...")

        expected_webhooks_by_url = associate_by_key(expected_org.get_webhooks(), lambda x: x["url"])
        github_webhooks = self.gh_client.get_webhooks(github_id)

        end = datetime.now()
        self.printer.print(f"webhooks: Read complete after {(end - start).total_seconds()}s")

        for github_webhook in github_webhooks:
            current_otterdog_webhook = mapping.map_github_org_webhook_data_to_otterdog(github_webhook)

            webhook_id = str(github_webhook["id"])
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

    def _process_single_repo(self, github_id: str, repo_name: str) -> (str, dict[str, Any]):
        repo_data = \
            self.gh_client.get_repo_data(github_id, repo_name)
        repo_data["branch_protection_rules"] = \
            self.gh_client.get_branch_protection_rules(github_id, repo_name)
        return repo_name, repo_data

    def _process_repositories(self, github_id: str, expected_org: org.Organization, diff_status: DiffStatus) -> None:
        start = datetime.now()
        self.printer.print(f"\nrepositories: Reading...")

        expected_repos_by_name = associate_by_key(expected_org.get_repos(), lambda x: x["name"])
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

        end = datetime.now()
        self.printer.print(f"repositories: Read complete after {(end - start).total_seconds()}s")

        for current_repo_name in current_repos:
            current_github_repo_data = current_github_repos[current_repo_name]
            current_branch_protection_rules = current_github_repo_data.pop("branch_protection_rules")

            current_repo_id = current_github_repo_data["node_id"]
            is_private = current_github_repo_data["private"]
            is_archived = current_github_repo_data["archived"]

            current_otterdog_repo_data = mapping.map_github_repo_data_to_otterdog(current_github_repo_data)

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

    def _process_branch_protection_rules(self,
                                         org_id: str,
                                         repo_name: str,
                                         repo_id: str,
                                         current_rules: list[dict[str, Any]],
                                         expected_repo: dict[str, Any],
                                         diff_status: DiffStatus) -> None:

        expected_branch_protection_rules_by_pattern = \
            associate_by_key(expected_repo.get("branch_protection_rules"), lambda x: x["pattern"])

        is_archived = expected_repo["archived"]
        if is_archived:
            if len(expected_branch_protection_rules_by_pattern) > 0:
                print_warn(f"branch_protection_rules specified for archived project, will be ignored.")
            return

        # only retrieve current rules if the repo_id is available, otherwise it's a new repo
        if repo_id:
            for current_rule in current_rules:
                rule_id = current_rule["id"]
                rule_pattern = current_rule["pattern"]
                expected_rule = expected_branch_protection_rules_by_pattern.get(rule_pattern)
                if expected_rule is None:
                    self.handle_extra_rule(org_id, repo_name, repo_id,
                                           schemas.get_items_contained_in_schema(current_rule,
                                                                                 schemas.BRANCH_PROTECTION_RULE_SCHEMA))
                    diff_status.extras += 1
                    continue

                modified_rule = {}
                for key, expected_value in expected_rule.items():
                    current_value = current_rule.get(key)
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
                                 modified_settings: dict[str, (Any, Any)]) -> int:
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
