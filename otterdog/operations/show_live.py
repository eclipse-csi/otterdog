#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from otterdog.config import OrganizationConfig
from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import GitHubProvider
from otterdog.utils import style

from . import Operation


class ShowLiveOperation(Operation):
    """
    Shows the current live configuration of organizations.
    """

    def __init__(self, no_web_ui: bool):
        super().__init__()
        self._no_web_ui = no_web_ui

    @property
    def no_web_ui(self) -> bool:
        return self._no_web_ui

    def pre_execute(self) -> None:
        self.printer.println("Showing live resources:")

    async def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"\nOrganization {style(org_config.name, bright=True)}[id={github_id}]")
        self.printer.level_up()

        try:
            try:
                credentials = self.config.get_credentials(org_config)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{str(e)}")
                return 1

            with GitHubProvider(credentials) as provider:
                if self.no_web_ui is True:
                    self.printer.print_warn(
                        "the Web UI will not be queried as '--no-web-ui' has been specified, "
                        "the resulting config will be incomplete."
                    )

                organization = await GitHubOrganization.load_from_provider(
                    github_id, jsonnet_config, provider, self.no_web_ui, self.printer
                )

            for model_object, parent_object in organization.get_model_objects():
                self.printer.println()
                model_header = model_object.get_model_header(parent_object)
                self.print_dict(model_object.to_model_dict(), model_header, "", "black")

            return 0

        finally:
            self.printer.level_down()
