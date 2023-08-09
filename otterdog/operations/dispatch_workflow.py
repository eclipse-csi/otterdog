# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from colorama import Style

from otterdog.config import OrganizationConfig
from otterdog.providers.github import Github
from otterdog.utils import print_error

from . import Operation


class DispatchWorkflowOperation(Operation):
    def __init__(self, repo_name: str, workflow_name: str):
        super().__init__()
        self.repo_name = repo_name
        self.workflow_name = workflow_name

    def pre_execute(self) -> None:
        self.printer.println(f"Dispatching workflows for the configuration at '{self.config.config_file}'")

    def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"Organization {Style.BRIGHT}{org_config.name}{Style.RESET_ALL}[id={github_id}]")
        self.printer.level_up()

        try:
            try:
                credentials = self.config.get_credentials(org_config)
            except RuntimeError as e:
                print_error(f"invalid credentials\n{str(e)}")
                return 1

            gh_client = Github(credentials)

            success = gh_client.dispatch_workflow(github_id, self.repo_name, self.workflow_name)
            if success is True:
                self.printer.println(f"workflow '{self.workflow_name}' dispatched for repo '{self.repo_name}'")
            else:
                self.printer.println(f"failed to dispatch workflow '{self.workflow_name}' for repo '{self.repo_name}'")

            return 0
        finally:
            self.printer.level_down()
