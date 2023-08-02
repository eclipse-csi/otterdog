# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from colorama import Style, Fore

from otterdog.config import OrganizationConfig
from otterdog.utils import jsonnet_evaluate_snippet

from . import Operation


class ShowDefaultOperation(Operation):
    def __init__(self):
        super().__init__()

    def pre_execute(self) -> None:
        self.printer.println(f"Showing defaults defined in configuration '{self.config.config_file}'")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"Organization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")
        self.printer.level_up()

        try:
            default_org = self.evaluate(jsonnet_config, f"{jsonnet_config.create_org}('<github-id>')")
            default_org_settings = {"settings": default_org["settings"]}
            self.printer.println()
            self.print_dict(
                default_org_settings, f"orgs.{jsonnet_config.create_org}('<github-id>') =", "", Fore.RED, ":", ","
            )

            default_repo = self.evaluate(jsonnet_config, f"{jsonnet_config.create_repo}('<repo-name>')")
            self.printer.println()
            self.print_dict(
                default_repo, f"orgs.{jsonnet_config.create_repo}('<repo-name>') =", "", Fore.BLACK, ":", ","
            )

            default_bpr = self.evaluate(jsonnet_config, f"{jsonnet_config.create_branch_protection_rule}('<pattern>')")
            self.printer.println()
            self.print_dict(
                default_bpr,
                f"orgs.{jsonnet_config.create_branch_protection_rule}('<pattern>') =",
                "",
                Fore.BLACK,
                ":",
                ",",
            )

            return 0

        finally:
            self.printer.level_down()

    @staticmethod
    def evaluate(jsonnet_config, function: str):
        try:
            snippet = f"(import '{jsonnet_config.template_file}').{function}"
            return jsonnet_evaluate_snippet(snippet)
        except RuntimeError as ex:
            raise RuntimeError(f"failed to evaluate snippet: {ex}")
