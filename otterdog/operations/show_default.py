#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from . import Operation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig


class ShowDefaultOperation(Operation):
    """
    Shows the default configuration for organizations.
    """

    def __init__(self, markdown: bool):
        super().__init__()
        self._markdown = markdown

    @property
    def markdown(self) -> bool:
        return self._markdown

    def pre_execute(self) -> None:
        if not self.markdown:
            self.printer.println("Showing defaults configurations:")

    async def execute(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> int:
        jsonnet_config = org_config.jsonnet_config
        await jsonnet_config.init_template()

        if not self.markdown:
            self._print_project_header(org_config, org_index, org_count)
            self.printer.level_up()

        try:
            default_org = self.evaluate(jsonnet_config, f"{jsonnet_config.create_org}('<project-name>', '<github-id>')")
            default_org_settings = {"settings": default_org["settings"]}
            self.printer.println()
            self._print_header("Organization Settings")
            self.print_dict(
                default_org_settings,
                f"orgs.{jsonnet_config.create_org}('<project-name>', '<github-id>') =",
                "",
                "red",
                ":",
                ",",
            )
            self._print_footer()

            default_org_role = self.evaluate(jsonnet_config, f"{jsonnet_config.create_org_role}('<name>')")
            self.printer.println()
            self._print_header("Organization Role")
            self.print_dict(
                default_org_role,
                f"orgs.{jsonnet_config.create_org_role}('<name>') =",
                "",
                "black",
                ":",
                ",",
            )
            self._print_footer()

            default_org_webhook = self.evaluate(jsonnet_config, f"{jsonnet_config.create_org_webhook}('<url>')")
            self.printer.println()
            self._print_header("Organization Webhook")
            self.print_dict(
                default_org_webhook,
                f"orgs.{jsonnet_config.create_org_webhook}('<url>') =",
                "",
                "black",
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
                "black",
                ":",
                ",",
            )
            self._print_footer()

            default_org_variable = self.evaluate(jsonnet_config, f"{jsonnet_config.create_org_variable}('<name>')")
            self.printer.println()
            self._print_header("Organization Variable")
            self.print_dict(
                default_org_variable,
                f"orgs.{jsonnet_config.create_org_variable}('<name>') =",
                "",
                "black",
                ":",
                ",",
            )
            self._print_footer()

            default_repo = self.evaluate(jsonnet_config, f"{jsonnet_config.create_repo}('<repo-name>')")
            self.printer.println()
            self._print_header("Repository")
            self.print_dict(default_repo, f"orgs.{jsonnet_config.create_repo}('<repo-name>') =", "", "black", ":", ",")
            self._print_footer()

            default_bpr = self.evaluate(jsonnet_config, f"{jsonnet_config.create_branch_protection_rule}('<pattern>')")
            self.printer.println()
            self._print_header("Branch Protection Rule")
            self.print_dict(
                default_bpr,
                f"orgs.{jsonnet_config.create_branch_protection_rule}('<pattern>') =",
                "",
                "black",
                ":",
                ",",
            )
            self._print_footer()

            default_ruleset = self.evaluate(jsonnet_config, f"{jsonnet_config.create_repo_ruleset}('<name>')")
            self.printer.println()
            self._print_header("Repository Ruleset")
            self.print_dict(
                default_ruleset,
                f"orgs.{jsonnet_config.create_repo_ruleset}('<name>') =",
                "",
                "black",
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
                "black",
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
                "black",
                ":",
                ",",
            )
            self._print_footer()

            default_repo_variable = self.evaluate(jsonnet_config, f"{jsonnet_config.create_repo_variable}('<name>')")
            self.printer.println()
            self._print_header("Repository Variable")
            self.print_dict(
                default_repo_variable,
                f"orgs.{jsonnet_config.create_repo_variable}('<name>') =",
                "",
                "black",
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
                "black",
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
                    f"""\
                === "{resource_name}"
                    ``` jsonnet\
                """
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
        from otterdog.utils import jsonnet_evaluate_snippet

        try:
            snippet = f"(import '{jsonnet_config.template_file}').{function}"
            return jsonnet_evaluate_snippet(snippet)
        except RuntimeError as ex:
            raise RuntimeError(f"failed to evaluate snippet: {ex}") from ex
