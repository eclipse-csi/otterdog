#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

import os
from abc import abstractmethod
from typing import Any

import organization as org
import utils
from config import OtterdogConfig, OrganizationConfig
from github import Github
from operation import Operation


class DiffOperation(Operation):
    def __init__(self, config: OtterdogConfig):
        self.config = config
        self.jsonnet_config = config.jsonnet_config
        self.gh_client = None

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        credentials = self.config.get_credentials(org_config)
        self.gh_client = Github(credentials)

        org_file_name = self.jsonnet_config.get_org_config_file(github_id)

        if not os.path.exists(org_file_name):
            msg = f"configuration file '{org_file_name}' for organization '{org_file_name}' does not exist"
            utils.exit_with_message(msg, 1)

        expected_org = org.load_from_file(github_id, self.jsonnet_config.get_org_config_file(github_id))
        expected_settings = expected_org.get_settings()

        # determine differences for settings.
        current_org_settings = self.gh_client.get_org_settings(github_id)

        differences = 0
        modified_settings = {}
        for key, expected_value in sorted(expected_settings.items()):
            if key not in current_org_settings:
                utils.print_warn(f"  unexpected key '{key}' found in configuration, skipping")
                continue

            current_value = current_org_settings.get(key)

            if current_value != expected_value:
                differences += 1
                modified_settings[key] = (expected_value, current_value)

        self.handle_modified_settings(github_id, modified_settings)

        # determine differences for webhooks.
        expected_webhooks_by_url = utils.associate_by_key(expected_org.get_webhooks(), lambda x: x["config"]["url"])
        current_webhooks = self.gh_client.get_webhooks(github_id)

        for webhook in current_webhooks:
            webhook_id = str(webhook["id"])
            webhook_url = webhook["config"]["url"]
            expected_webhook = expected_webhooks_by_url.get(webhook_url)
            if expected_webhook is None:
                utils.print_warn(f"no configuration found for webhook with url '{webhook_url}'")
                differences += 1
                continue

            modified_webhook = {}
            current_webhook_config = webhook["config"]
            # only config settings are supported to be verified for now.
            for key, expected_value in expected_webhook["config"].items():
                current_value = current_webhook_config.get(key)

                if expected_value != current_value:
                    differences += 1
                    modified_webhook[key] = (expected_value, current_value)

            expected_webhooks_by_url.pop(webhook_url)

            self.handle_modified_webhook(github_id, webhook_id, modified_webhook)

        for webhook_url, webhook in expected_webhooks_by_url.items():
            differences += 1
            self.handle_new_webhook(github_id, webhook)

        # determine differences for repositories
        expected_repos_by_name = utils.associate_by_key(expected_org.get_repos(), lambda x: x["name"])
        current_repos = self.gh_client.get_repos(github_id)

        for current_repo in current_repos:
            repo_id = current_repo["node_id"]
            repo_name = current_repo["name"]
            expected_repo = expected_repos_by_name.get(repo_name)
            if expected_repo is None:
                utils.print_warn(f"no configuration found for repo with name '{repo_name}'")
                differences += 1
                continue

            modified_repo = {}
            for key, expected_value in expected_repo.items():
                current_value = current_repo.get(key)

                if key == "branch_protection_rules":
                    differences += self._process_branch_protection_rules(github_id, repo_name, repo_id, expected_repo)
                else:
                    if expected_value != current_value:
                        differences += 1
                        modified_repo[key] = (expected_value, current_value)

            expected_repos_by_name.pop(repo_name)
            self.handle_modified_repo(github_id, repo_name, modified_repo)

        for repo_name, repo in expected_repos_by_name.items():
            differences += 1
            # TODO: process branch protection rules for new repo's as well
            self.handle_new_repo(github_id, repo)

        self.handle_finish(differences)
        return differences

    def _process_branch_protection_rules(self,
                                         org_id: str,
                                         repo_name: str,
                                         repo_id,
                                         expected_repo: dict[str, Any]) -> int:
        differences = 0

        expected_branch_protection_rules_by_pattern = \
            utils.associate_by_key(expected_repo.get("branch_protection_rules"), lambda x: x["pattern"])

        current_rules = self.gh_client.get_branch_protection_rules(org_id, repo_name)
        for current_rule in current_rules:
            rule_id = current_rule["id"]
            rule_pattern = current_rule["pattern"]
            expected_rule = expected_branch_protection_rules_by_pattern.get(rule_pattern)
            if expected_rule is None:
                msg = f"no configuration found for branch protection rule with pattern '{rule_pattern}'"
                utils.print_warn(msg)
                differences += 1
                continue

            modified_rule = {}
            for key, expected_value in expected_rule.items():
                current_value = current_rule.get(key)

                if expected_value != current_value:
                    differences += 1
                    modified_rule[key] = (expected_value, current_value)

            expected_branch_protection_rules_by_pattern.pop(rule_pattern)
            self.handle_modified_rule(org_id, repo_name, rule_pattern, rule_id, modified_rule)

        for rule_pattern, rule in expected_branch_protection_rules_by_pattern.items():
            differences += 1
            self.handle_new_rule(org_id, repo_name, repo_id, rule)

        return differences

    @abstractmethod
    def handle_modified_settings(self,
                                 org_id: str,
                                 modified_settings: dict[str, (Any, Any)]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_modified_webhook(self,
                                org_id: str,
                                webhook_id: str,
                                modified_webhook: dict[str, (Any, Any)]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_new_webhook(self,
                           org_id: str,
                           data: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_modified_repo(self,
                             org_id: str,
                             repo_name: str,
                             modified_repo: dict[str, (Any, Any)]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_new_repo(self,
                        org_id: str,
                        data: dict[str, Any]) -> None:
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
    def handle_new_rule(self, org_id: str, repo_name: str, repo_id: str, data: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_finish(self, differences: int) -> None:
        raise NotImplementedError
