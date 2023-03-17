# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os

import jq
from colorama import Fore, Style

from . import organization as org
from .config import OtterdogConfig, OrganizationConfig
from .operation import Operation
from .utils import IndentingPrinter


class ValidateOperation(Operation):
    def __init__(self):
        self.config = None
        self.jsonnet_config = None
        self._printer = None

    @property
    def printer(self) -> IndentingPrinter:
        return self._printer

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        self.config = config
        self.jsonnet_config = self.config.jsonnet_config
        self._printer = printer

    def pre_execute(self) -> None:
        self.printer.print(f"Validating configuration at '{self.config.config_file}'")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id

        self.printer.print(f"Organization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")
        self.printer.level_up()

        try:
            org_file_name = self.jsonnet_config.get_org_config_file(github_id)

            if not os.path.exists(org_file_name):
                self.printer.print_warn(f"configuration file '{org_file_name}' does not yet exist, run fetch first")
                return 1

            try:
                organization = org.load_from_file(github_id, self.jsonnet_config.get_org_config_file(github_id))
            except RuntimeError as ex:
                self.printer.print_error(f"Validation failed\nfailed to load configuration: {str(ex)}")
                return 1

            validation_errors = self.validate(organization)

            if validation_errors == 0:
                self.printer.print(f"{Fore.GREEN}Validation succeeded{Style.RESET_ALL}")
            else:
                self.printer.print(f"{Fore.RED}Validation failed{Style.RESET_ALL}")

            return validation_errors
        finally:
            self.printer.level_down()

    def validate(self, organization: org.Organization) -> int:
        validation_errors = 0

        settings = organization.get_settings()

        # enabling dependabot implicitly enables the dependency graph,
        # disabling the dependency graph in the configuration will result in inconsistencies after
        # applying the configuration, warn the user about it.
        dependabot_alerts_enabled = \
            settings.get("dependabot_alerts_enabled_for_new_repositories") is True
        dependabot_security_updates_enabled = \
            settings.get("dependabot_security_updates_enabled_for_new_repositories") is True

        dependency_graph_disabled = \
            settings.get("dependency_graph_enabled_for_new_repositories") is False

        if (dependabot_alerts_enabled or dependabot_security_updates_enabled) and dependency_graph_disabled:
            self.printer.print_error(f"enabling dependabot_alerts or dependabot_security_updates implicitly"
                                     f" enables dependency_graph_enabled_for_new_repositories")
            validation_errors += 1

        if dependabot_security_updates_enabled and not dependabot_alerts_enabled:
            self.printer.print_error(f"enabling dependabot_security_updates also enables dependabot_alerts")
            validation_errors += 1

        webhooks = organization.get_webhooks()

        for webhook in webhooks:
            secret = jq.compile('.config.secret // ""').input(webhook).first()
            if secret and all(ch == '*' for ch in secret):
                url = jq.compile('.config.url // ""').input(webhook).first()
                self.printer.print_error(f"webhook with url '{url}' uses a dummy secret '{secret}'")
                validation_errors += 1

        repos = organization.get_repos()

        web_commit_signoff_required = settings.get("web_commit_signoff_required", False)
        members_can_fork_private_repositories = settings.get("members_can_fork_private_repositories", None)

        for repo in repos:
            repo_name = repo["name"]
            is_private = repo["private"]

            has_wiki = repo.get("has_wiki", False)
            if is_private and has_wiki is True:
                self.printer.print_warn(
                    f"private repo[name=\"{repo_name}\"] has 'has_wiki' enabled which is requires at least"
                    f"GitHub Team billing.")
                validation_errors += 1

            allow_forking = repo.get("allow_forking", False)
            if is_private and members_can_fork_private_repositories is False and allow_forking is True:
                self.printer.print_error(
                    f"private repo[name=\"{repo_name}\"] has 'allow_forking' enabled while the organization setting"
                    f" 'members_can_fork_private_repositories' is disabled.")
                validation_errors += 1

            repo_web_commit_signoff_required = repo.get("web_commit_signoff_required", False)
            if repo_web_commit_signoff_required is False and web_commit_signoff_required is True:
                self.printer.print_error(
                    f"repo[name=\"{repo_name}\"] has 'web_commit_signoff_required' disabled while "
                    f"the organization requires it.")
                validation_errors += 1

            branch_protection_rules = repo.get("branch_protection_rules")
            if branch_protection_rules is not None:
                for rule in branch_protection_rules:
                    rule_pattern = rule["pattern"]
                    requiresApprovingReviews = rule.get("requiresApprovingReviews")
                    requiredApprovingReviewCount = rule.get("requiredApprovingReviewCount")

                    if (requiresApprovingReviews is True) and \
                            (requiredApprovingReviewCount is None or requiredApprovingReviewCount < 0):
                        self.printer.print_error(
                            f"branch_protection_rule[repo=\"{repo_name}\",pattern=\"{rule_pattern}\"] has"
                            f" 'requiredApprovingReviews' enabled but 'requiredApprovingReviewCount' is not set.")
                        validation_errors += 1

        return validation_errors
