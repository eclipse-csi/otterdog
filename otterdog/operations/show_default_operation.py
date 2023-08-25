# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import textwrap

from colorama import Style, Fore

from otterdog.config import OrganizationConfig

from . import Operation
from ..utils import jsonnet_evaluate_snippet


class ShowDefaultOperation(Operation):
    def __init__(self, markdown: bool):
        super().__init__()
        self.markdown = markdown

    def pre_execute(self) -> None:
        if not self.markdown:
            self.printer.println(f"Showing defaults defined in configuration '{self.config.config_file}'")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        if not self.markdown:
            self.printer.println(f"\nOrganization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")
            self.printer.level_up()

        try:
            default_org = self.evaluate(jsonnet_config, f"{jsonnet_config.create_org}('<github-id>')")
            default_org_settings = {"settings": default_org["settings"]}
            self.printer.println()
            self._print_header("Organization Settings")
            self.print_dict(
                default_org_settings, f"orgs.{jsonnet_config.create_org}('<github-id>') =", "", Fore.RED, ":", ","
            )
            self._print_footer()

            default_org_webhook = self.evaluate(jsonnet_config, f"{jsonnet_config.create_org_webhook}('<url>')")
            self.printer.println()
            self._print_header("Organization Webhook")
            self.print_dict(
                default_org_webhook,
                f"orgs.{jsonnet_config.create_org_webhook}('<url>') =",
                "",
                Fore.BLACK,
                ":",
                ",",
            )
            self._print_footer()

            default_org_secret = self.evaluate(jsonnet_config, f"{jsonnet_config.create_org_secret}('<name>')")
            self.printer.println()
            self._print_header("Organization Secret")
            self.print_dict(
                default_org_secret,
                f"orgs.{jsonnet_config.create_org_secret}('<name>') =",
                "",
                Fore.BLACK,
                ":",
                ",",
            )
            self._print_footer()

            default_repo = self.evaluate(jsonnet_config, f"{jsonnet_config.create_repo}('<repo-name>')")
            self.printer.println()
            self._print_header("Repository")
            self.print_dict(
                default_repo, f"orgs.{jsonnet_config.create_repo}('<repo-name>') =", "", Fore.BLACK, ":", ","
            )
            self._print_footer()

            default_bpr = self.evaluate(jsonnet_config, f"{jsonnet_config.create_branch_protection_rule}('<pattern>')")
            self.printer.println()
            self._print_header("Branch Protection Rule")
            self.print_dict(
                default_bpr,
                f"orgs.{jsonnet_config.create_branch_protection_rule}('<pattern>') =",
                "",
                Fore.BLACK,
                ":",
                ",",
            )
            self._print_footer()

            default_repo_webhook = self.evaluate(jsonnet_config, f"{jsonnet_config.create_repo_webhook}('<url>')")
            self.printer.println()
            self._print_header("Repository Webhook")
            self.print_dict(
                default_repo_webhook,
                f"orgs.{jsonnet_config.create_repo_webhook}('<url>') =",
                "",
                Fore.BLACK,
                ":",
                ",",
            )
            self._print_footer()

            default_repo_secret = self.evaluate(jsonnet_config, f"{jsonnet_config.create_repo_secret}('<name>')")
            self.printer.println()
            self._print_header("Repository Secret")
            self.print_dict(
                default_repo_secret,
                f"orgs.{jsonnet_config.create_repo_secret}('<name>') =",
                "",
                Fore.BLACK,
                ":",
                ",",
            )
            self._print_footer()

            default_repo_env = self.evaluate(jsonnet_config, f"{jsonnet_config.create_environment}('<name>')")
            self.printer.println()
            self._print_header("Environment")
            self.print_dict(
                default_repo_env,
                f"orgs.{jsonnet_config.create_environment}('<name>') =",
                "",
                Fore.BLACK,
                ":",
                ",",
            )
            self._print_footer()

            return 0

        finally:
            if not self.markdown:
                self.printer.level_down()

    def _print_header(self, resource_name: str):
        if self.markdown:
            self.printer.println(
                textwrap.dedent(
                    f'''\
                === "{resource_name}"
                    ``` jsonnet\
                '''
                )
            )
            self.printer.level_up()
            self.printer.level_up()

    def _print_footer(self):
        if self.markdown:
            self.printer.println("```")
            self.printer.level_down()
            self.printer.level_down()

    @staticmethod
    def evaluate(jsonnet_config, function: str):
        try:
            snippet = f"(import '{jsonnet_config.template_file}').{function}"
            return jsonnet_evaluate_snippet(snippet)
        except RuntimeError as ex:
            raise RuntimeError(f"failed to evaluate snippet: {ex}")
