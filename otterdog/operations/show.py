#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import textwrap
from io import StringIO
from os import path
from typing import TYPE_CHECKING

from aiofiles import open, os, ospath

from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import IndentingPrinter, is_set_and_valid

from . import Operation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig
    from otterdog.models import ModelObject
    from otterdog.models.repository import Repository


class ShowOperation(Operation):
    """
    Shows the local configuration of an organization.
    """

    def __init__(self, markdown: bool, output_dir: str):
        super().__init__()
        self._markdown = markdown
        self._output_dir = output_dir

    @property
    def markdown(self) -> bool:
        return self._markdown

    @property
    def output_dir(self) -> str:
        return self._output_dir

    def pre_execute(self) -> None:
        if not self.markdown:
            self.printer.println("Showing organization resources:")

    async def execute(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        await jsonnet_config.init_template()

        if not self.markdown or self.printer.is_info_enabled():
            self._print_project_header(org_config, org_index, org_count)
            self.printer.level_up()

        try:
            org_file_name = jsonnet_config.org_config_file
            if not await self.check_config_file_exists(org_file_name):
                return 1

            try:
                organization = GitHubOrganization.load_from_file(github_id, org_file_name)
            except RuntimeError as ex:
                self.printer.print_error(f"failed to load configuration: {ex!s}")
                return 1

            if not self.markdown:
                self._print_classic(organization)
            else:
                await self._print_markdown(organization)

            return 0

        finally:
            if not self.markdown:
                self.printer.level_down()

    def _print_classic(self, organization: GitHubOrganization) -> None:
        for model_object, parent_object in organization.get_model_objects():
            self.printer.println()
            model_header = model_object.get_model_header(parent_object)
            self.print_dict(model_object.to_model_dict(), model_header, "", "black")

    async def _print_markdown(self, organization: GitHubOrganization) -> None:
        if not await ospath.exists(self.output_dir):
            await os.makedirs(self.output_dir, exist_ok=True)

        writer = StringIO()
        self.printer = IndentingPrinter(writer, spaces_per_level=4)

        self.printer.println(
            textwrap.dedent(
                """\
                ---
                hide:
                  - navigation
                ---
                """
            )
        )

        self.printer.println("# Current configuration")
        self.printer.println('=== "Organization Settings"')
        self.printer.level_up()
        self._print_model_object(organization.settings)
        self.printer.level_down()

        self.printer.println('=== "Organization Webhooks"')
        self.printer.level_up()
        if len(organization.webhooks) > 0:
            self.printer.println("| URL | Uses SSL | Secret | Resolved Secret |")
            self.printer.println("| :-- | :------: | :----: | :-------------: |")

            for webhook in organization.webhooks:
                uses_ssl = ":white_check_mark:" if webhook.insecure_ssl == "0" else ":x:"
                has_secret = ":white_check_mark:" if is_set_and_valid(webhook.secret) else ":x:"
                resolved_secret = ":white_check_mark:" if not webhook.has_dummy_secret() else ":regional_indicator_x:"

                self.printer.println(f"| {webhook.url} | {uses_ssl} | {has_secret} | {resolved_secret} |")
        else:
            self.printer.println("No webhooks.")
        self.printer.level_down()

        self.printer.println('=== "Organization Secrets"')
        self.printer.level_up()
        if len(organization.secrets) > 0:
            self.printer.println("| Name | Resolved Secret |")
            self.printer.println("| :--- | :-------------: |")

            for secret in organization.secrets:
                resolved_secret = ":white_check_mark:" if not secret.has_dummy_secret() else ":regional_indicator_x:"

                self.printer.println(f"| {secret.name} | {resolved_secret} |")
        else:
            self.printer.println("No secrets.")
        self.printer.level_down()

        self.printer.println('=== "Organization Variables"')
        self.printer.level_up()
        if len(organization.variables) > 0:
            self.printer.println("| Name | Value |")
            self.printer.println("| :--- | :---- |")

            for variable in organization.variables:
                self.printer.println(f"| {variable.name} | {variable.value} |")
        else:
            self.printer.println("No variables.")
        self.printer.level_down()

        self.printer.println('=== "Repositories"')
        self.printer.level_up()

        self.printer.println("| Repository | Branch Protections | Secrets | Variables | Webhooks | Secret Scanning |")
        self.printer.println("| :--------- | :----------------: | :-----: | :-------: | :------: | :-------------: |")

        for repo in organization.repositories:
            has_branch_protections = (
                ":white_check_mark:" if len(repo.branch_protection_rules) > 0 or len(repo.rulesets) > 0 else ":x:"
            )
            has_secrets = ":white_check_mark:" if len(repo.secrets) > 0 else ":regional_indicator_x:"
            has_variables = ":white_check_mark:" if len(repo.variables) > 0 else ":regional_indicator_x:"
            has_webhooks = ":white_check_mark:" if len(repo.webhooks) > 0 else ":regional_indicator_x:"
            secret_scanning = ":white_check_mark:" if repo.secret_scanning == "enabled" else ":x:"

            label = ":material-archive:" if repo.archived else ""
            github_url = f"https://github.com/{organization.github_id}/{repo.name}"

            self.printer.println(
                f"| [{repo.name}](repo-{repo.name}.md) {label} "
                f"[:octicons-link-external-16:]({github_url}){{:target='_blank'}} | "
                f"{has_branch_protections} | {has_secrets} | {has_variables} | {has_webhooks} | "
                f"{secret_scanning} |"
            )

        self.printer.level_down()

        async with open(path.join(self.output_dir, "configuration.md"), "w") as file:
            await file.write(writer.getvalue())

        for repo in organization.repositories:
            await self._print_repo_markdown(organization, repo)

    async def _print_repo_markdown(self, organization: GitHubOrganization, repo: Repository) -> None:
        writer = StringIO()
        self.printer = IndentingPrinter(writer, spaces_per_level=4)

        self.printer.println(
            textwrap.dedent(
                """\
                ---
                hide:
                  - navigation
                ---
                """
            )
        )

        self.printer.println(f"# Repo [{repo.name}](https://github.com/{organization.github_id}/{repo.name})")
        self.printer.println('=== "Settings"')
        self.printer.level_up()
        self._print_model_object(repo)
        self.printer.level_down()

        self.printer.println('=== "Webhooks"')
        self.printer.level_up()

        if len(repo.webhooks) > 0:
            self.printer.println("| URL | Uses SSL | Secret | Resolved Secret |")
            self.printer.println("| :-- | :------: | :----: | :-------------: |")

            for webhook in repo.webhooks:
                uses_ssl = ":white_check_mark:" if webhook.insecure_ssl == "0" else ":x:"
                has_secret = ":white_check_mark:" if is_set_and_valid(webhook.secret) else ":x:"
                resolved_secret = ":white_check_mark:" if not webhook.has_dummy_secret() else ":regional_indicator_x:"

                self.printer.println(f"| {webhook.url} | {uses_ssl} | {has_secret} | {resolved_secret} |")
        else:
            self.printer.println("No webhooks.")
        self.printer.level_down()

        self.printer.println('=== "Secrets"')
        self.printer.level_up()

        if len(repo.secrets) > 0:
            self.printer.println("| Name | Resolved Secret |")
            self.printer.println("| :--- | :-------------: |")

            for secret in repo.secrets:
                resolved_secret = ":white_check_mark:" if not secret.has_dummy_secret() else ":regional_indicator_x:"

                self.printer.println(f"| {secret.name} | {resolved_secret} |")
        else:
            self.printer.println("No secrets.")
        self.printer.level_down()

        self.printer.println('=== "Variables"')
        self.printer.level_up()
        if len(repo.variables) > 0:
            self.printer.println("| Name | Value |")
            self.printer.println("| :--- | :---- |")

            for variable in repo.variables:
                self.printer.println(f"| {variable.name} | {variable.value} |")
        else:
            self.printer.println("No variables.")
        self.printer.level_down()

        self.printer.println('=== "Branch Protection Rules"')
        self.printer.level_up()
        if len(repo.branch_protection_rules) > 0:
            for bpr in repo.branch_protection_rules:
                self._print_model_object(bpr)
        else:
            self.printer.println("No branch protection rules.")
        self.printer.level_down()

        self.printer.println('=== "Rulesets"')
        self.printer.level_up()
        if len(repo.rulesets) > 0:
            for ruleset in repo.rulesets:
                self._print_model_object(ruleset)
        else:
            self.printer.println("No rulesets.")
        self.printer.level_down()

        async with open(path.join(self.output_dir, f"repo-{repo.name}.md"), "w") as file:
            await file.write(writer.getvalue())

    def _print_model_object(self, model_object: ModelObject, include_nested: bool = False):
        self.printer.println("``` jsonnet")
        self.print_dict(
            model_object.to_model_dict(include_nested_models=include_nested),
            model_object.model_object_name,
            "",
            "",
            ":",
            ",",
        )
        self.printer.println("```")
