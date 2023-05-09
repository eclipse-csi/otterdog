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

from otterdog.config import OtterdogConfig, OrganizationConfig
from otterdog.models.github_organization import GitHubOrganization, load_github_organization_from_file, \
    load_repos_from_provider
from otterdog.models.branch_protection_rule import BranchProtectionRule
from otterdog.models.organization_settings import OrganizationSettings
from otterdog.models.organization_webhook import OrganizationWebhook
from otterdog.models.repository import Repository
from otterdog.providers.github import Github
from otterdog.utils import IndentingPrinter, associate_by_key, print_warn, Change, is_unset, is_set_and_valid

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
            expected_org = \
                load_github_organization_from_file(github_id, org_file_name, self.config, self.resolve_secrets())
        except RuntimeError as e:
            self.printer.print_error(f"failed to load configuration\n{str(e)}")
            return 1

        # We validate the configuration first and only calculate a plan if
        # there are no validation errors.
        validation_warnings, validation_errors = self._validator.validate(expected_org)
        validation_failures = validation_warnings + validation_errors
        if validation_failures > 0:
            self.printer.print("Planning aborted due to validation failures.")
            return validation_failures

        diff_status = DiffStatus()

        modified_org_settings = self._process_settings(github_id, expected_org, diff_status)

        # add a warning that otterdog potentially must be run a second time
        # to fully apply all setting.
        if "web_commit_signoff_required" in modified_org_settings:
            change = modified_org_settings["web_commit_signoff_required"]
            if change.to_value is False:
                if self.verbose_output():
                    print_warn(f"Setting 'web_commit_signoff_required' setting has been disabled on "
                               f"organization level. \nThe effective setting on repo level can only be "
                               f"determined once this change has been applied.\n"
                               f"You need to run otterdog another time to fully ensure "
                               f"that the correct configuration is applied.")

        self._process_webhooks(github_id, expected_org, diff_status)
        self._process_repositories(github_id, expected_org, modified_org_settings, diff_status)

        self.handle_finish(github_id, diff_status)
        return 0

    def _process_settings(self,
                          github_id: str,
                          expected_org: GitHubOrganization,
                          diff_status: DiffStatus) -> dict[str, Change[Any]]:
        expected_org_settings = expected_org.settings

        start = datetime.now()
        if self.verbose_output():
            self.printer.print(f"organization settings: Reading...")

        # filter out web settings if --no-web-ui is used
        expected_settings_keys = expected_org_settings.keys(for_diff=True)
        if self.config.no_web_ui:
            expected_settings_keys = {x for x in expected_settings_keys if not self.gh_client.is_web_org_setting(x)}

        # determine differences for settings.
        current_org_settings = self.get_current_org_settings(github_id, expected_settings_keys)

        if self.verbose_output():
            end = datetime.now()
            self.printer.print(f"organization settings: Read complete after {(end - start).total_seconds()}s")

        modified_settings = expected_org_settings.get_difference_from(current_org_settings)
        if len(modified_settings) > 0:
            # some settings might be read-only, collect the correct number of changes
            # to be executed based on the operations to be performed.
            differences = \
                self.handle_modified_settings(github_id,
                                              modified_settings,
                                              expected_org_settings)
            diff_status.differences += differences

        return modified_settings

    def get_current_org_settings(self, github_id: str, settings_keys: set[str]) -> OrganizationSettings:
        # determine differences for settings.
        current_github_org_settings = self.gh_client.get_org_settings(github_id, settings_keys)
        return OrganizationSettings.from_provider(current_github_org_settings)

    def _process_webhooks(self, github_id: str, expected_org: GitHubOrganization, diff_status: DiffStatus) -> None:
        start = datetime.now()
        if self.verbose_output():
            self.printer.print(f"\nwebhooks: Reading...")

        expected_webhooks_by_url = associate_by_key(expected_org.webhooks, lambda x: x.url)
        current_webhooks = self.get_current_webhooks(github_id)

        if self.verbose_output():
            end = datetime.now()
            self.printer.print(f"webhooks: Read complete after {(end - start).total_seconds()}s")

        for current_webhook in current_webhooks:
            webhook_url = current_webhook.url

            expected_webhook = expected_webhooks_by_url.get(webhook_url)
            if expected_webhook is None:
                self.handle_extra_webhook(github_id, current_webhook)
                diff_status.extras += 1
                continue

            modified_webhook = expected_webhook.get_difference_from(current_webhook)

            # special handling for secrets:
            #   if a secret was present by now its gone or vice-versa,
            #   include it in the diff view.
            expected_secret = expected_webhook.secret
            current_secret = current_webhook.secret

            if ((expected_secret is not None and is_unset(current_secret)) or
                    (expected_secret is None and is_set_and_valid(current_secret))):
                modified_webhook["secret"] = Change(current_secret, expected_secret)

            if len(modified_webhook) > 0:
                self.handle_modified_webhook(github_id,
                                             current_webhook.id,
                                             webhook_url,
                                             modified_webhook,
                                             expected_webhook)

                diff_status.differences += len(modified_webhook)

            expected_webhooks_by_url.pop(webhook_url)

        for webhook_url, webhook in expected_webhooks_by_url.items():
            self.handle_new_webhook(github_id, webhook)
            diff_status.additions += 1

    def get_current_webhooks(self, github_id: str) -> list[OrganizationWebhook]:
        github_webhooks = self.gh_client.get_webhooks(github_id)
        return [OrganizationWebhook.from_provider(webhook) for webhook in github_webhooks]

    def _process_repositories(self,
                              github_id: str,
                              expected_org: GitHubOrganization,
                              modified_org_settings: dict[str, Change[Any]],
                              diff_status: DiffStatus) -> None:

        expected_repos_by_name = associate_by_key(expected_org.repositories, lambda x: x.name)
        current_repos = self.get_current_repos(github_id)

        for current_repo in current_repos:
            current_repo_name = current_repo.name
            expected_repo = expected_repos_by_name.get(current_repo_name)

            if expected_repo is None:
                self.handle_extra_repo(github_id, current_repo)
                diff_status.extras += 1
                continue

            # special handling for some keys that can be set organization wide
            if "web_commit_signoff_required" in modified_org_settings:
                change = modified_org_settings["web_commit_signoff_required"]
                if change.to_value is True:
                    current_repo.web_commit_signoff_required = change.to_value

            modified_repo = expected_repo.get_difference_from(current_repo)

            if len(modified_repo) > 0:
                self.handle_modified_repo(github_id, current_repo_name, modified_repo)
                diff_status.differences += len(modified_repo)

            self._process_branch_protection_rules(github_id,
                                                  current_repo,
                                                  expected_repo,
                                                  diff_status)

            expected_repos_by_name.pop(current_repo_name)

        for repo_name, repo in expected_repos_by_name.items():
            self.handle_new_repo(github_id, repo)

            diff_status.additions += 1

            if len(repo.branch_protection_rules) > 0:
                self._process_branch_protection_rules(github_id, None, repo, diff_status)

    def get_current_repos(self, github_id: str) -> list[Repository]:
        if self.verbose_output():
            printer = self.printer
        else:
            printer = None

        return load_repos_from_provider(github_id, self.gh_client, printer)

    def _process_branch_protection_rules(self,
                                         org_id: str,
                                         current_repo: Repository | None,
                                         expected_repo: Repository,
                                         diff_status: DiffStatus) -> None:

        expected_branch_protection_rules_by_pattern = \
            associate_by_key(expected_repo.branch_protection_rules, lambda x: x.pattern)

        is_archived = expected_repo.archived
        if is_archived is True:
            if len(expected_branch_protection_rules_by_pattern) > 0:
                if self.verbose_output():
                    print_warn(f"branch_protection_rules specified for archived project, will be ignored.")
            return

        # only retrieve current rules if the current_repo is available, otherwise it's a new repo
        if current_repo is not None:
            for current_rule in current_repo.branch_protection_rules:
                rule_pattern = current_rule.pattern

                expected_rule = expected_branch_protection_rules_by_pattern.get(rule_pattern)
                if expected_rule is None:
                    self.handle_extra_rule(org_id, current_repo.name, current_repo.id, current_rule)
                    diff_status.extras += 1
                    continue

                modified_rule = expected_rule.get_difference_from(current_rule)

                if len(modified_rule) > 0:
                    self.handle_modified_rule(org_id, current_repo.name, rule_pattern, current_rule.id, modified_rule)
                    diff_status.differences += len(modified_rule)

                expected_branch_protection_rules_by_pattern.pop(rule_pattern)

        for rule_pattern, rule in expected_branch_protection_rules_by_pattern.items():
            if current_repo is not None:
                repo_id = current_repo.node_id
            else:
                repo_id = None

            self.handle_new_rule(org_id, expected_repo.name, repo_id, rule)
            diff_status.additions += 1

    @abstractmethod
    def handle_modified_settings(self,
                                 org_id: str,
                                 modified_settings: dict[str, Change[Any]],
                                 full_settings: OrganizationSettings) -> int:
        raise NotImplementedError

    @abstractmethod
    def handle_modified_webhook(self,
                                org_id: str,
                                webhook_id: str,
                                webhook_url: str,
                                modified_webhook: dict[str, Change[Any]],
                                webhook: OrganizationWebhook) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_extra_webhook(self, org_id: str, webhook: OrganizationWebhook) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_new_webhook(self, org_id: str, webhook: OrganizationWebhook) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_modified_repo(self,
                             org_id: str,
                             repo_name: str,
                             modified_repo: dict[str, Change[Any]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_extra_repo(self, org_id: str, repo: Repository) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_new_repo(self, org_id: str, repo: Repository) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_modified_rule(self,
                             org_id: str,
                             repo_name: str,
                             rule_pattern: str,
                             rule_id: str,
                             modified_rule: dict[str, Change[Any]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_extra_rule(self, org_id: str, repo_name: str, repo_id: str, bpr: BranchProtectionRule) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_new_rule(self, org_id: str, repo_name: str, repo_id: str, bpr: BranchProtectionRule) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_finish(self, org_id: str, diff_status: DiffStatus) -> None:
        raise NotImplementedError
