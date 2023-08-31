# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from typing import Any, Optional, cast

from colorama import Style

from otterdog.config import OtterdogConfig
from otterdog.models.branch_protection_rule import BranchProtectionRule
from otterdog.models.environment import Environment
from otterdog.models.organization_settings import OrganizationSettings
from otterdog.models.organization_webhook import OrganizationWebhook
from otterdog.models.organization_secret import OrganizationSecret
from otterdog.models.repository import Repository
from otterdog.models.repo_secret import RepositorySecret
from otterdog.models.repo_webhook import RepositoryWebhook
from otterdog.utils import IndentingPrinter, Change, get_approval

from .diff_operation import DiffStatus
from .plan_operation import PlanOperation
from ..models import ModelObject


class ApplyOperation(PlanOperation):
    def __init__(
        self,
        force_processing: bool,
        no_web_ui: bool,
        update_webhooks: bool,
        update_secrets: bool,
        update_filter: str,
        delete_resources: bool,
    ):
        super().__init__(no_web_ui, update_webhooks, update_secrets, update_filter)

        self._force_processing = force_processing
        self._delete_resources = delete_resources

        self._org_settings_to_update: dict[str, Change[Any]] = {}
        self._modified_org_webhooks: dict[int, OrganizationWebhook]
        self._added_org_webhooks: list[OrganizationWebhook]
        self._deleted_org_webhooks: list[OrganizationWebhook]
        self._modified_org_secrets: dict[str, OrganizationSecret]
        self._added_org_secrets: list[OrganizationSecret]
        self._deleted_org_secrets: list[OrganizationSecret]
        self._modified_repos: dict[str, dict[str, Change[Any]]]
        self._added_repos: list[Repository]
        self._deleted_repos: list[Repository]
        self._modified_repo_webhooks: list[tuple[str, int, RepositoryWebhook]]
        self._added_repo_webhooks: list[tuple[str, RepositoryWebhook]]
        self._deleted_repo_webhooks: list[tuple[str, RepositoryWebhook]]
        self._modified_repo_secrets: list[tuple[str, str, RepositorySecret]]
        self._added_repo_secrets: list[tuple[str, RepositorySecret]]
        self._deleted_repo_secrets: list[tuple[str, RepositorySecret]]
        self._modified_environments: list[tuple[str, str, dict[str, Change[Any]]]]
        self._added_environments: list[tuple[str, Environment]]
        self._deleted_environments: list[tuple[str, Environment]]
        self._modified_rules: list[tuple[str, str, str, dict[str, Change[Any]]]]
        self._added_rules: list[tuple[str, Optional[str], BranchProtectionRule]]
        self._deleted_rules: list[tuple[str, BranchProtectionRule]]

        self._reset()

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        super().init(config, printer)

    def pre_execute(self) -> None:
        self.printer.println(f"Apply changes for configuration at '{self.config.config_file}'")
        self.print_legend()

    def _reset(self) -> None:
        self._org_settings_to_update = {}
        self._modified_org_webhooks = {}
        self._added_org_webhooks = []
        self._deleted_org_webhooks = []
        self._modified_org_secrets = {}
        self._added_org_secrets = []
        self._deleted_org_secrets = []
        self._modified_repos = {}
        self._added_repos = []
        self._deleted_repos = []
        self._modified_repo_webhooks = []
        self._added_repo_webhooks = []
        self._deleted_repo_webhooks = []
        self._modified_repo_secrets = []
        self._added_repo_secrets = []
        self._deleted_repo_secrets = []
        self._modified_environments = []
        self._added_environments = []
        self._deleted_environments = []
        self._modified_rules = []
        self._added_rules = []
        self._deleted_rules = []

    def handle_add_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: Optional[ModelObject] = None,
    ) -> None:
        super().handle_add_object(org_id, model_object, parent_object)

        if isinstance(model_object, OrganizationWebhook):
            self._added_org_webhooks.append(model_object)
        elif isinstance(model_object, OrganizationSecret):
            self._added_org_secrets.append(model_object)
        elif isinstance(model_object, Repository):
            self._added_repos.append(model_object)
        elif isinstance(model_object, RepositoryWebhook):
            repo_name = cast(Repository, parent_object).name
            self._added_repo_webhooks.append((repo_name, model_object))
        elif isinstance(model_object, RepositorySecret):
            repo_name = cast(Repository, parent_object).name
            self._added_repo_secrets.append((repo_name, model_object))
        elif isinstance(model_object, Environment):
            repo_name = cast(Repository, parent_object).name
            self._added_environments.append((repo_name, model_object))
        elif isinstance(model_object, BranchProtectionRule):
            repo_name = cast(Repository, parent_object).name
            repo_node_id = cast(Repository, parent_object).node_id
            self._added_rules.append((repo_name, repo_node_id, model_object))
        else:
            raise ValueError(f"unexpected model_object of type '{type(model_object)}'")

    def handle_delete_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: Optional[ModelObject] = None,
    ) -> None:
        super().handle_delete_object(org_id, model_object, parent_object)

        if isinstance(model_object, OrganizationWebhook):
            self._deleted_org_webhooks.append(model_object)
        elif isinstance(model_object, OrganizationSecret):
            self._deleted_org_secrets.append(model_object)
        elif isinstance(model_object, Repository):
            self._deleted_repos.append(model_object)
        elif isinstance(model_object, RepositoryWebhook):
            repo_name = cast(Repository, parent_object).name
            self._deleted_repo_webhooks.append((repo_name, model_object))
        elif isinstance(model_object, RepositorySecret):
            repo_name = cast(Repository, parent_object).name
            self._deleted_repo_secrets.append((repo_name, model_object))
        elif isinstance(model_object, Environment):
            repo_name = cast(Repository, parent_object).name
            self._deleted_environments.append((repo_name, model_object))
        elif isinstance(model_object, BranchProtectionRule):
            repo_name = cast(Repository, parent_object).name
            self._deleted_rules.append((repo_name, model_object))
        else:
            raise ValueError(f"unexpected model_object of type '{type(model_object)}'")

    def handle_modified_object(
        self,
        org_id: str,
        modified_object: dict[str, Change[Any]],
        forced_update: bool,
        current_object: ModelObject,
        expected_object: ModelObject,
        parent_object: Optional[ModelObject] = None,
    ) -> int:
        modified = super().handle_modified_object(
            org_id,
            modified_object,
            forced_update,
            current_object,
            expected_object,
            parent_object,
        )

        if isinstance(current_object, OrganizationSettings):
            self._org_settings_to_update = modified_object
        elif isinstance(current_object, OrganizationWebhook):
            self._modified_org_webhooks[current_object.id] = cast(OrganizationWebhook, expected_object)
        elif isinstance(current_object, OrganizationSecret):
            self._modified_org_secrets[current_object.name] = cast(OrganizationSecret, expected_object)
        elif isinstance(current_object, Repository):
            self._modified_repos[current_object.name] = modified_object
        elif isinstance(current_object, RepositoryWebhook):
            repo_name = cast(Repository, parent_object).name
            self._modified_repo_webhooks.append(
                (repo_name, current_object.id, cast(RepositoryWebhook, expected_object))
            )
        elif isinstance(current_object, RepositorySecret):
            repo_name = cast(Repository, parent_object).name
            self._modified_repo_secrets.append(
                (
                    repo_name,
                    current_object.name,
                    cast(RepositorySecret, expected_object),
                )
            )
        elif isinstance(current_object, Environment):
            repo_name = cast(Repository, parent_object).name
            self._modified_environments.append((repo_name, current_object.name, modified_object))
        elif isinstance(current_object, BranchProtectionRule):
            repo_name = cast(Repository, parent_object).name
            self._modified_rules.append((repo_name, current_object.pattern, current_object.id, modified_object))
        else:
            raise ValueError(f"unexpected current_object of type '{type(current_object)}'")

        return modified

    def handle_finish(self, org_id: str, diff_status: DiffStatus) -> None:
        try:
            self.printer.println()

            if diff_status.total_changes(self._delete_resources) == 0:
                self.printer.println("No changes required.")
                if not self._delete_resources and diff_status.deletions > 0:
                    self.printer.println(
                        f"{diff_status.deletions} resource(s) would be deleted with " f"flag '--delete-resources'."
                    )
                return

            if not self._force_processing:
                if diff_status.deletions > 0 and not self._delete_resources:
                    self.printer.println("No resource will be removed, use flag '--delete-resources' to delete them.\n")

                self.printer.println(
                    f"{Style.BRIGHT}Do you want to perform these actions?\n"
                    f"  Only 'yes' or 'y' will be accepted to approve.\n"
                )

                self.printer.print(f"  {Style.BRIGHT}Enter a value:{Style.RESET_ALL} ")
                if not get_approval():
                    self.printer.println("\nApply cancelled.")
                    return

            # update organization settings
            if len(self._org_settings_to_update) > 0:
                github_settings = OrganizationSettings.changes_to_provider(
                    org_id, self._org_settings_to_update, self.gh_client
                )
                self.gh_client.update_org_settings(org_id, github_settings)

            # update organization webhooks
            for webhook_id, org_webhook in self._modified_org_webhooks.items():
                self.gh_client.update_org_webhook(
                    org_id, webhook_id, org_webhook.to_provider_data(org_id, self.gh_client)
                )

            # add organization webhooks
            for org_webhook in self._added_org_webhooks:
                self.gh_client.add_org_webhook(org_id, org_webhook.to_provider_data(org_id, self.gh_client))

            # update organization secrets
            for secret_name, org_secret in self._modified_org_secrets.items():
                self.gh_client.update_org_secret(
                    org_id, secret_name, org_secret.to_provider_data(org_id, self.gh_client)
                )

            # add organization secrets
            for org_secret in self._added_org_secrets:
                self.gh_client.add_org_secret(org_id, org_secret.to_provider_data(org_id, self.gh_client))

            # update repos
            for repo_name, repo_data in self._modified_repos.items():
                github_repo = Repository.changes_to_provider(org_id, repo_data, self.gh_client)
                self.gh_client.update_repo(org_id, repo_name, github_repo)

            # add repos
            for repo in self._added_repos:
                self.gh_client.add_repo(
                    org_id,
                    repo.to_provider_data(org_id, self.gh_client),
                    repo.template_repository,
                    repo.post_process_template_content,
                    repo.auto_init,
                )

            # update repo webhooks
            for repo_name, webhook_id, repo_webhook in self._modified_repo_webhooks:
                self.gh_client.update_repo_webhook(
                    org_id,
                    repo_name,
                    webhook_id,
                    repo_webhook.to_provider_data(org_id, self.gh_client),
                )

            # add repo webhooks
            for repo_name, repo_webhook in self._added_repo_webhooks:
                self.gh_client.add_repo_webhook(
                    org_id, repo_name, repo_webhook.to_provider_data(org_id, self.gh_client)
                )

            # update repo secrets
            for repo_name, secret_name, repo_secret in self._modified_repo_secrets:
                self.gh_client.update_repo_secret(
                    org_id,
                    repo_name,
                    secret_name,
                    repo_secret.to_provider_data(org_id, self.gh_client),
                )

            # add repo secrets
            for repo_name, repo_secret in self._added_repo_secrets:
                self.gh_client.add_repo_secret(org_id, repo_name, repo_secret.to_provider_data(org_id, self.gh_client))

            # update environments
            for repo_name, env_name, modified_env in self._modified_environments:
                github_env = Environment.changes_to_provider(org_id, modified_env, self.gh_client)
                self.gh_client.update_repo_environment(org_id, repo_name, env_name, github_env)

            # add environments
            for repo_name, env in self._added_environments:
                self.gh_client.add_repo_environment(
                    org_id,
                    repo_name,
                    env.name,
                    env.to_provider_data(org_id, self.gh_client),
                )

            # update branch protection rules
            for repo_name, rule_pattern, rule_id, modified_rule in self._modified_rules:
                github_rule = BranchProtectionRule.changes_to_provider(org_id, modified_rule, self.gh_client)
                self.gh_client.update_branch_protection_rule(org_id, repo_name, rule_pattern, rule_id, github_rule)

            # add branch protection rules
            for repo_name, repo_node_id, rule in self._added_rules:
                self.gh_client.add_branch_protection_rule(
                    org_id,
                    repo_name,
                    repo_node_id,
                    rule.to_provider_data(org_id, self.gh_client),
                )

            if self._delete_resources:
                for org_webhook in self._deleted_org_webhooks:
                    self.gh_client.delete_org_webhook(org_id, org_webhook.id, org_webhook.url)

                for org_secret in self._deleted_org_secrets:
                    self.gh_client.delete_org_secret(org_id, org_secret.name)

                for repo in self._deleted_repos:
                    self.gh_client.delete_repo(org_id, repo.name)

                for repo_name, repo_webhook in self._deleted_repo_webhooks:
                    self.gh_client.delete_repo_webhook(org_id, repo_name, repo_webhook.id, repo_webhook.url)

                for repo_name, repo_secret in self._deleted_repo_secrets:
                    self.gh_client.delete_repo_secret(org_id, repo_name, repo_secret.name)

                for repo_name, repo_env in self._deleted_environments:
                    self.gh_client.delete_repo_environment(org_id, repo_name, repo_env.name)

                for repo_name, rule in self._deleted_rules:
                    self.gh_client.delete_branch_protection_rule(org_id, repo_name, rule.pattern, rule.id)

            delete_snippet = "deleted" if self._delete_resources else "live resources ignored"

            self.printer.println(
                f"{Style.BRIGHT}Executed plan:{Style.RESET_ALL} {diff_status.additions} added, "
                f"{diff_status.differences} changed, "
                f"{diff_status.deletions} {delete_snippet}."
            )
        finally:
            self._reset()
