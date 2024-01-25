#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os.path
from typing import Optional

from otterdog.config import OrganizationConfig
from otterdog.providers.github import GitHubProvider
from otterdog.utils import style

from . import Operation


class PushOperation(Operation):
    """
    Pushes a local configuration of an organization to its meta-data repository.
    """

    def __init__(self, push_message: Optional[str]):
        super().__init__()
        self._push_message = push_message

    @property
    def push_message(self) -> Optional[str]:
        return self._push_message

    def pre_execute(self) -> None:
        self.printer.println("Pushing organization configurations:")

    async def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"\nOrganization {style(org_config.name, bright=True)}[id={github_id}]")

        org_file_name = jsonnet_config.org_config_file

        if not os.path.exists(org_file_name):
            self.printer.print_error(
                f"configuration file '{org_file_name}' does not yet exist, run fetch-config or import first"
            )
            return 1

        self.printer.level_up()

        try:
            try:
                credentials = self.config.get_credentials(org_config, only_token=True)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{str(e)}")
                return 1

            with open(org_file_name, "r") as file:
                content = file.read()

            with open(jsonnet_config.jsonnet_bundle_file, "r") as file:
                bundle_content = file.read()

            with GitHubProvider(credentials) as provider:
                try:
                    updated_files = []
                    updated = False

                    if await provider.update_content(
                        org_config.github_id,
                        org_config.config_repo,
                        f"otterdog/{github_id}.jsonnet",
                        content,
                        self.push_message,
                    ):
                        updated_files.append(f"otterdog/{github_id}.jsonnet")
                        updated = True

                    if await provider.update_content(
                        org_config.github_id,
                        org_config.config_repo,
                        "otterdog/jsonnetfile.json",
                        bundle_content,
                        self.push_message,
                    ):
                        updated_files.append("otterdog/jsonnetfile.json")
                        updated |= True

                    if await provider.update_content(
                        org_config.github_id,
                        org_config.config_repo,
                        "otterdog/jsonnetfile.lock.json",
                        "",
                        self.push_message,
                    ):
                        updated_files.append("otterdog/jsonnetfile.lock.json")
                        updated |= True

                except RuntimeError as e:
                    self.printer.print_error(
                        f"failed to push definition to repo '{org_config.github_id}/{org_config.config_repo}': {str(e)}"
                    )
                    return 1

            if updated:
                self.printer.println(
                    f"organization definition pushed to repo '{org_config.github_id}/{org_config.config_repo}': "
                )
                for updated_file in updated_files:
                    self.printer.println(f"  - '{updated_file}'")
            else:
                self.printer.println("no changes, nothing pushed")

            return 0
        finally:
            self.printer.level_down()
