# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os
from abc import abstractmethod
from datetime import datetime
from typing import Any

from colorama import Style

import organization as org
import schemas
from config import OtterdogConfig, OrganizationConfig
from github import Github
from operation import Operation
from utils import IndentingPrinter, associate_by_key


class DiffStatus:
    def __init__(self):
        self.additions = 0
        self.differences = 0
        self.extras = 0

    def total_changes(self) -> int:
        return self.additions + self.differences


class DiffOperation(Operation):
    def __init__(self):
        self.config = None
        self.jsonnet_config = None
        self.gh_client = None
        self._printer = None

    @property
    def printer(self) -> IndentingPrinter:
        return self._printer

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        self.config = config
        self.jsonnet_config = self.config.jsonnet_config
        self._printer = printer

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
            expected_org = org.load_from_file(github_id, self.jsonnet_config.get_org_config_file(github_id))
        except RuntimeError as e:
            self.printer.print_error(f"failed to load configuration\n{str(e)}")
            return 1

        diff_status = DiffStatus()

        self._process_settings(github_id, expected_org, diff_status)
        self._process_webhooks(github_id, expected_org, diff_status)
        self._process_repositories(github_id, expected_org, diff_status)

        self.handle_finish(diff_status)
        return diff_status.total_changes()

    def _process_settings(self, github_id: str, expected_org: org.Organization, diff_status: DiffStatus) -> None:
        expected_settings = expected_org.get_settings()

        start = datetime.now()
        self.printer.print(f"organization settings: Reading...")

        # determine differences for settings.
        current_org_settings = self.gh_client.get_org_settings(github_id, expected_settings.keys())

        end = datetime.now()
        self.printer.print(f"organization settings: Read complete after {(end - start).total_seconds()}s")

        modified_settings = {}
        for key, expected_value in sorted(expected_settings.items()):
            if key not in current_org_settings:
                self.printer.print_warn(f"unexpected key '{key}' found in configuration, skipping")
                continue

            current_value = current_org_settings.get(key)

            if current_value != expected_value:
                diff_status.differences += 1
                modified_settings[key] = (expected_value, current_value)

        if len(modified_settings) > 0:
            self.handle_modified_settings(github_id, modified_settings)

    def _process_webhooks(self, github_id: str, expected_org: org.Organization, diff_status: DiffStatus) -> None:
        start = datetime.now()
        self.printer.print(f"\nwebhooks: Reading...")

        expected_webhooks_by_url = associate_by_key(expected_org.get_webhooks(), lambda x: x["config"]["url"])
        current_webhooks = self.gh_client.get_webhooks(github_id)

        end = datetime.now()
        self.printer.print(f"webhooks: Read complete after {(end - start).total_seconds()}s")

        for webhook in current_webhooks:
            webhook_id = str(webhook["id"])
            webhook_url = webhook["config"]["url"]
            expected_webhook = expected_webhooks_by_url.get(webhook_url)
            if expected_webhook is None:
                self.handle_extra_webhook(github_id,
                                          schemas.get_items_contained_in_schema(webhook, schemas.WEBHOOK_SCHEMA))
                diff_status.extras += 1
                continue

            # TODO: improve handling of config.secret

            modified_webhook = {}
            for key, expected_value in expected_webhook.items():
                current_value = webhook.get(key)

                if expected_value != current_value:
                    modified_webhook[key] = (expected_value, current_value)
                    diff_status.differences += 1

            if len(modified_webhook) > 0:
                self.handle_modified_webhook(github_id, webhook_id, webhook_url, modified_webhook, expected_webhook)

            expected_webhooks_by_url.pop(webhook_url)

        for webhook_url, webhook in expected_webhooks_by_url.items():
            self.handle_new_webhook(github_id, webhook)
            diff_status.additions += 1

    def _process_repositories(self, github_id: str, expected_org: org.Organization, diff_status: DiffStatus) -> None:
        start = datetime.now()
        self.printer.print(f"\nrepositories: Reading...")

        expected_repos_by_name = associate_by_key(expected_org.get_repos(), lambda x: x["name"])
        current_repos = self.gh_client.get_repos(github_id)

        end = datetime.now()
        self.printer.print(f"repositories: Read complete after {(end - start).total_seconds()}s")

        for current_repo_name in current_repos:
            current_repo_data = self.gh_client.get_repo_data(github_id, current_repo_name)
            expected_repo = expected_repos_by_name.get(current_repo_name)

            if expected_repo is None:
                self.handle_extra_repo(github_id, schemas.get_items_contained_in_schema(current_repo_data,
                                                                                        schemas.REPOSITORY_SCHEMA))
                diff_status.extras += 1
                continue

            current_repo_id = current_repo_data["node_id"]

            modified_repo = {}
            for key, expected_value in expected_repo.items():
                # branch protection rules are treated separately.
                if key == "branch_protection_rules":
                    continue

                current_value = current_repo_data.get(key)
                if expected_value != current_value:
                    diff_status.differences += 1
                    modified_repo[key] = (expected_value, current_value)

            if len(modified_repo) > 0:
                self.handle_modified_repo(github_id, current_repo_name, modified_repo)

            self._process_branch_protection_rules(github_id,
                                                  current_repo_name,
                                                  current_repo_id,
                                                  expected_repo,
                                                  diff_status)

            expected_repos_by_name.pop(current_repo_name)

        for repo_name, repo in expected_repos_by_name.items():
            new_repo = repo.copy()
            branch_protection_rules = new_repo.pop("branch_protection_rules")
            self.handle_new_repo(github_id, new_repo)

            diff_status.additions += 1

            if len(branch_protection_rules) > 0:
                self._process_branch_protection_rules(github_id, repo_name, "", repo, diff_status)

    def _process_branch_protection_rules(self,
                                         org_id: str,
                                         repo_name: str,
                                         repo_id: str,
                                         expected_repo: dict[str, Any],
                                         diff_status: DiffStatus) -> None:

        expected_branch_protection_rules_by_pattern = \
            associate_by_key(expected_repo.get("branch_protection_rules"), lambda x: x["pattern"])

        # only retrieve current rules if the repo_id is available, otherwise it's a new repo
        if repo_id:
            current_rules = self.gh_client.get_branch_protection_rules(org_id, repo_name)
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
                                 modified_settings: dict[str, (Any, Any)]) -> None:
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
    def handle_finish(self, diff_status: DiffStatus) -> None:
        raise NotImplementedError
