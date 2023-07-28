# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os
from abc import abstractmethod
from typing import Any, Optional, TypeVar

from colorama import Style

from otterdog.config import OtterdogConfig, OrganizationConfig
from otterdog.jsonnet import JsonnetConfig
from otterdog.models import ModelObject
from otterdog.models.github_organization import GitHubOrganization
from otterdog.models.repository import Repository
from otterdog.models.secret import Secret
from otterdog.models.webhook import Webhook
from otterdog.providers.github import Github
from otterdog.utils import (
    IndentingPrinter,
    associate_by_key,
    multi_associate_by_key,
    print_warn,
    print_error,
    Change,
    is_unset,
    is_set_and_valid,
    is_info_enabled,
)

from . import Operation
from .validate_operation import ValidateOperation

WT = TypeVar("WT", bound=Webhook)
ST = TypeVar("ST", bound=Secret)


class DiffStatus:
    def __init__(self):
        self.additions = 0
        self.differences = 0
        self.deletions = 0

    def total_changes(self, include_deletions: bool) -> int:
        if include_deletions:
            return self.additions + self.differences + self.deletions
        else:
            return self.additions + self.differences


class DiffOperation(Operation):
    def __init__(self, no_web_ui: bool, update_webhooks: bool, update_secrets: bool):
        super().__init__()

        self.no_web_ui = no_web_ui
        self.update_webhooks = update_webhooks
        self.update_secrets = update_secrets
        self._gh_client: Optional[Github] = None
        self._validator = ValidateOperation()

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        super().init(config, printer)
        self._validator.init(config, printer)

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id

        self.printer.println(f"Organization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")

        try:
            self._gh_client = self.setup_github_client(org_config)
        except RuntimeError as e:
            print_error(f"invalid credentials\n{str(e)}")
            return 1

        self.printer.level_up()

        try:
            return self._generate_diff(org_config)
        finally:
            self.printer.level_down()

    def setup_github_client(self, org_config: OrganizationConfig) -> Github:
        return Github(self.config.get_credentials(org_config))

    @property
    def gh_client(self) -> Github:
        assert self._gh_client is not None
        return self._gh_client

    def verbose_output(self):
        return True

    def resolve_secrets(self) -> bool:
        return True

    def _generate_diff(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        org_file_name = jsonnet_config.org_config_file

        if not os.path.exists(org_file_name):
            print_error(f"configuration file '{org_file_name}' does not yet exist, run fetch-config or import first")
            return 1

        try:
            expected_org = self.load_expected_org(github_id, org_file_name)
        except RuntimeError as e:
            print_error(f"failed to load configuration\n{str(e)}")
            return 1

        # We validate the configuration first and only calculate a plan if
        # there are no validation errors.
        (
            validation_infos,
            validation_warnings,
            validation_errors,
        ) = self._validator.validate(expected_org, jsonnet_config.template_dir)
        if validation_errors > 0:
            self.printer.println("Planning aborted due to validation errors.")
            return validation_errors

        if validation_infos > 0 and not is_info_enabled():
            self.printer.println(
                f"there have been {validation_infos} validation infos, "
                f"enable verbose output with '-v' to to display them."
            )

        try:
            current_org = self.load_current_org(github_id, jsonnet_config)
        except RuntimeError as e:
            print_error(f"failed to load current configuration\n{str(e)}")
            return 1

        diff_status = DiffStatus()

        modified_org_settings = self._process_org_settings(github_id, expected_org, current_org, diff_status)

        # add a warning that otterdog potentially must be run a second time
        # to fully apply all setting.
        if "web_commit_signoff_required" in modified_org_settings:
            change = modified_org_settings["web_commit_signoff_required"]
            if change.to_value is False:
                if self.verbose_output():
                    print_warn(
                        "Setting 'web_commit_signoff_required' setting has been disabled on "
                        "organization level. \nThe effective setting on repo level can only be "
                        "determined once this change has been applied.\n"
                        "You need to run otterdog another time to fully ensure "
                        "that the correct configuration is applied."
                    )

        self._process_org_webhooks(github_id, expected_org, current_org, diff_status)
        self._process_org_secrets(github_id, expected_org, current_org, diff_status)
        self._process_repositories(github_id, expected_org, current_org, modified_org_settings, diff_status)

        self.handle_finish(github_id, diff_status)
        return 0

    def load_expected_org(self, github_id: str, org_file_name: str) -> GitHubOrganization:
        return GitHubOrganization.load_from_file(github_id, org_file_name, self.config, self.resolve_secrets())

    def load_current_org(self, github_id: str, jsonnet_config: JsonnetConfig) -> GitHubOrganization:
        return GitHubOrganization.load_from_provider(
            github_id, jsonnet_config, self.gh_client, self.no_web_ui, self.printer
        )

    def _process_org_settings(
        self,
        github_id: str,
        expected_org: GitHubOrganization,
        current_org: GitHubOrganization,
        diff_status: DiffStatus,
    ) -> dict[str, Change[Any]]:
        expected_org_settings = expected_org.settings
        current_org_settings = current_org.settings

        modified_settings: dict[str, Change[Any]] = expected_org_settings.get_difference_from(current_org_settings)
        if len(modified_settings) > 0:
            # some settings might be read-only, collect the correct number of changes
            # to be executed based on the operations to be performed.
            diff_status.differences += self.handle_modified_object(
                github_id,
                modified_settings,
                False,
                current_org_settings,
                expected_org_settings,
            )

        return modified_settings

    def _process_org_webhooks(
        self,
        github_id: str,
        expected_org: GitHubOrganization,
        current_org: GitHubOrganization,
        diff_status: DiffStatus,
    ) -> None:
        expected_webhooks_by_all_urls = multi_associate_by_key(expected_org.webhooks, Webhook.get_all_urls)
        expected_webhooks_by_url = associate_by_key(expected_org.webhooks, lambda x: x.url)
        self._process_webhooks(
            github_id,
            expected_webhooks_by_all_urls,
            expected_webhooks_by_url,
            current_org.webhooks,
            None,
            diff_status,
        )

    def _process_org_secrets(
        self,
        github_id: str,
        expected_org: GitHubOrganization,
        current_org: GitHubOrganization,
        diff_status: DiffStatus,
    ) -> None:
        expected_secrets_by_name = associate_by_key(expected_org.secrets, lambda x: x.name)
        self._process_secrets(github_id, expected_secrets_by_name, current_org.secrets, None, diff_status)

    def _process_repositories(
        self,
        github_id: str,
        expected_org: GitHubOrganization,
        current_org: GitHubOrganization,
        modified_org_settings: dict[str, Change[Any]],
        diff_status: DiffStatus,
    ) -> None:
        expected_repos_by_all_names = multi_associate_by_key(expected_org.repositories, Repository.get_all_names)
        expected_repos_by_name = associate_by_key(expected_org.repositories, lambda x: x.name)
        current_repos = current_org.repositories

        has_organization_projects_disabled = expected_org.settings.has_organization_projects is False

        for current_repo in current_repos:
            current_repo_name = current_repo.name
            expected_repo = expected_repos_by_all_names.get(current_repo_name)

            if expected_repo is None:
                self.handle_delete_object(github_id, current_repo)
                diff_status.deletions += 1
                continue

            # special handling for some keys that can be set organization wide
            if "web_commit_signoff_required" in modified_org_settings:
                change = modified_org_settings["web_commit_signoff_required"]
                if change.to_value is True:
                    current_repo.web_commit_signoff_required = change.to_value

            modified_repo: dict[str, Change[Any]] = expected_repo.get_difference_from(current_repo)

            # special handling for some keys that can be disabled on organization level
            # TODO: make this cleaner
            if "has_projects" in modified_repo and has_organization_projects_disabled:
                modified_repo.pop("has_projects")

            if "gh_pages_source_branch" in modified_repo:
                modified_repo["gh_pages_source_path"] = Change(
                    expected_repo.gh_pages_source_path, expected_repo.gh_pages_source_path
                )

            if len(modified_repo) > 0:
                diff_status.differences += self.handle_modified_object(
                    github_id, modified_repo, False, current_repo, expected_repo
                )

            self._process_repo_webhooks(github_id, current_repo, expected_repo, diff_status)
            self._process_repo_secrets(github_id, current_repo, expected_repo, diff_status)
            self._process_environments(github_id, current_repo, expected_repo, diff_status)
            self._process_branch_protection_rules(github_id, current_repo, expected_repo, diff_status)

            # pop the already handled repos
            for name in expected_repo.get_all_names():
                expected_repos_by_all_names.pop(name)
            expected_repos_by_name.pop(expected_repo.name)

        for repo_name, repo in expected_repos_by_name.items():
            self.handle_add_object(github_id, repo)

            diff_status.additions += 1

            if len(repo.webhooks) > 0:
                self._process_repo_webhooks(github_id, None, repo, diff_status)

            if len(repo.secrets) > 0:
                self._process_repo_secrets(github_id, None, repo, diff_status)

            if len(repo.environments) > 0:
                self._process_environments(github_id, None, repo, diff_status)

            if len(repo.branch_protection_rules) > 0:
                self._process_branch_protection_rules(github_id, None, repo, diff_status)

    def _process_branch_protection_rules(
        self,
        org_id: str,
        current_repo: Repository | None,
        expected_repo: Repository,
        diff_status: DiffStatus,
    ) -> None:
        expected_branch_protection_rules_by_pattern = associate_by_key(
            expected_repo.branch_protection_rules, lambda x: x.pattern
        )

        # ignore branch protection rules for archived projects.
        if expected_repo.archived is True:
            return

        # only retrieve current rules if the current_repo is available, otherwise it's a new repo
        current_rules = current_repo.branch_protection_rules if current_repo is not None else []
        for current_rule in current_rules:
            rule_pattern = current_rule.pattern

            expected_rule = expected_branch_protection_rules_by_pattern.get(rule_pattern)
            if expected_rule is None:
                self.handle_delete_object(org_id, current_rule, current_repo)
                diff_status.deletions += 1
                continue

            modified_rule: dict[str, Change[Any]] = expected_rule.get_difference_from(current_rule)

            if len(modified_rule) > 0:
                # we know that the current repo is not None
                assert current_repo is not None

                diff_status.differences += self.handle_modified_object(
                    org_id,
                    modified_rule,
                    False,
                    current_rule,
                    expected_rule,
                    current_repo,
                )

            expected_branch_protection_rules_by_pattern.pop(rule_pattern)

        for rule_pattern, rule in expected_branch_protection_rules_by_pattern.items():
            repo = expected_repo if current_repo is None else current_repo
            self.handle_add_object(org_id, rule, repo)
            diff_status.additions += 1

    def _process_repo_webhooks(
        self,
        org_id: str,
        current_repo: Repository | None,
        expected_repo: Repository,
        diff_status: DiffStatus,
    ) -> None:
        expected_webhooks_by_all_urls = multi_associate_by_key(expected_repo.webhooks, Webhook.get_all_urls)
        expected_webhooks_by_url = associate_by_key(expected_repo.webhooks, lambda x: x.url)
        current_repo_webhooks = current_repo.webhooks if current_repo is not None else []
        repo = expected_repo if current_repo is None else current_repo
        self._process_webhooks(
            org_id,
            expected_webhooks_by_all_urls,
            expected_webhooks_by_url,
            current_repo_webhooks,
            repo,
            diff_status,
        )

    def _process_repo_secrets(
        self,
        org_id: str,
        current_repo: Repository | None,
        expected_repo: Repository,
        diff_status: DiffStatus,
    ) -> None:
        expected_secrets_by_name = associate_by_key(expected_repo.secrets, lambda x: x.name)
        current_repo_secrets = current_repo.secrets if current_repo is not None else []
        repo = expected_repo if current_repo is None else current_repo
        self._process_secrets(org_id, expected_secrets_by_name, current_repo_secrets, repo, diff_status)

    def _process_webhooks(
        self,
        org_id: str,
        expected_webhooks_by_all_urls: dict[str, WT],
        expected_webhooks_by_url: dict[str, WT],
        current_webhooks: list[WT],
        parent_object: Optional[ModelObject],
        diff_status: DiffStatus,
    ) -> None:
        for current_webhook in current_webhooks:
            webhook_url = current_webhook.url

            expected_webhook = expected_webhooks_by_all_urls.get(webhook_url)
            if expected_webhook is None:
                self.handle_delete_object(org_id, current_webhook, parent_object)
                diff_status.deletions += 1
                continue

            # pop the already handled webhooks
            for url in expected_webhook.get_all_urls():
                expected_webhooks_by_all_urls.pop(url)
            expected_webhooks_by_url.pop(expected_webhook.url)

            # any webhook that contains a dummy secret will be skipped.
            if expected_webhook.has_dummy_secret():
                continue

            # if webhooks shall be updated and the webhook contains a valid secret perform a forced update.
            if self.update_webhooks and is_set_and_valid(expected_webhook.secret):
                model_dict = expected_webhook.to_model_dict()
                modified_webhook: dict[str, Change[Any]] = {k: Change(v, v) for k, v in model_dict.items()}

                diff_status.differences += self.handle_modified_object(
                    org_id,
                    modified_webhook,
                    True,
                    current_webhook,
                    expected_webhook,
                    parent_object,
                )
                continue

            modified_webhook = expected_webhook.get_difference_from(current_webhook)

            if not is_unset(expected_webhook.secret):
                # special handling for secrets:
                #   if a secret was present by now its gone or vice-versa,
                #   include it in the diff view.
                expected_secret = expected_webhook.secret
                current_secret = current_webhook.secret

                def has_unresolved_secret(secret: Optional[str]):
                    return secret is not None and self.resolve_secrets() is False

                # if there are different unresolved secrets, display changes
                has_different_unresolved_secrets = (
                    has_unresolved_secret(expected_secret)
                    and has_unresolved_secret(current_secret)
                    and expected_secret != current_secret
                )

                if (
                    (expected_secret is not None and current_secret is None)
                    or (expected_secret is None and current_secret is not None)
                    or has_different_unresolved_secrets
                ):
                    modified_webhook["secret"] = Change(current_secret, expected_secret)

            if len(modified_webhook) > 0:
                diff_status.differences += self.handle_modified_object(
                    org_id,
                    modified_webhook,
                    False,
                    current_webhook,
                    expected_webhook,
                    parent_object,
                )

        for webhook_url, webhook in expected_webhooks_by_url.items():
            self.handle_add_object(org_id, webhook, parent_object)
            diff_status.additions += 1

    def _process_secrets(
        self,
        org_id: str,
        expected_secrets_by_name: dict[str, ST],
        current_secrets: list[ST],
        parent_object: Optional[ModelObject],
        diff_status: DiffStatus,
    ) -> None:
        for current_secret in current_secrets:
            secret_name = current_secret.name

            expected_secret = expected_secrets_by_name.get(secret_name)
            if expected_secret is None:
                self.handle_delete_object(org_id, current_secret, parent_object)
                diff_status.deletions += 1
                continue

            # pop the already handled secret
            expected_secrets_by_name.pop(expected_secret.name)

            # any secret that contains a dummy value will be skipped.
            if expected_secret.has_dummy_secret():
                continue

            # if secrets shall be updated and the secret contains a valid secret perform a forced update.
            if self.update_secrets:
                model_dict = expected_secret.to_model_dict()
                modified_secret: dict[str, Change[Any]] = {k: Change(v, v) for k, v in model_dict.items()}

                diff_status.differences += self.handle_modified_object(
                    org_id,
                    modified_secret,
                    True,
                    current_secret,
                    expected_secret,
                    parent_object,
                )
                continue

            modified_secret = expected_secret.get_difference_from(current_secret)

            if not is_unset(expected_secret.value):
                expected_secret_value = expected_secret.value
                current_secret_value = current_secret.value

                def has_unresolved_secret(secret_value: Optional[str]):
                    return secret_value is not None and self.resolve_secrets() is False

                # if there are different unresolved secrets, display changes
                if (
                    has_unresolved_secret(expected_secret_value)
                    and has_unresolved_secret(current_secret_value)
                    and expected_secret_value != current_secret_value
                ):
                    modified_secret["value"] = Change(current_secret_value, expected_secret_value)

            if len(modified_secret) > 0:
                diff_status.differences += self.handle_modified_object(
                    org_id,
                    modified_secret,
                    False,
                    current_secret,
                    expected_secret,
                    parent_object,
                )

        for secret_name, secret in expected_secrets_by_name.items():
            self.handle_add_object(org_id, secret, parent_object)
            diff_status.additions += 1

    def _process_environments(
        self,
        org_id: str,
        current_repo: Repository | None,
        expected_repo: Repository,
        diff_status: DiffStatus,
    ) -> None:
        expected_environments_by_name = associate_by_key(expected_repo.environments, lambda x: x.name)

        # only retrieve current rules if the current_repo is available, otherwise it's a new repo
        current_environments = current_repo.environments if current_repo is not None else []
        for current_env in current_environments:
            env_name = current_env.name

            expected_env = expected_environments_by_name.get(env_name)
            if expected_env is None:
                self.handle_delete_object(org_id, current_env, current_repo)
                diff_status.deletions += 1
                continue

            modified_env: dict[str, Change[Any]] = expected_env.get_difference_from(current_env)

            if len(modified_env) > 0:
                # we know that the current repo is not None
                assert current_repo is not None

                diff_status.differences += self.handle_modified_object(
                    org_id, modified_env, False, current_env, expected_env, current_repo
                )

            expected_environments_by_name.pop(env_name)

        for env_name, env in expected_environments_by_name.items():
            repo = expected_repo if current_repo is None else current_repo
            self.handle_add_object(org_id, env, repo)
            diff_status.additions += 1

    @abstractmethod
    def handle_add_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: Optional[ModelObject] = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_delete_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: Optional[ModelObject] = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def handle_modified_object(
        self,
        org_id: str,
        modified_object: dict[str, Change[Any]],
        forced_update: bool,
        current_object: ModelObject,
        expected_object: ModelObject,
        parent_object: Optional[ModelObject] = None,
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    def handle_finish(self, org_id: str, diff_status: DiffStatus) -> None:
        raise NotImplementedError
