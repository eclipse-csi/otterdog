#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from otterdog.config import OrganizationConfig
from otterdog.providers.github import GitHubProvider
from otterdog.utils import style

from . import Operation


class DispatchWorkflowOperation(Operation):
    """
    Dispatches a specified workflow for an organization repo.
    """

    def __init__(self, repo_name: str, workflow_name: str):
        super().__init__()
        self._repo_name = repo_name
        self._workflow_name = workflow_name

    @property
    def repo_name(self) -> str:
        return self._repo_name

    @property
    def workflow_name(self) -> str:
        return self._workflow_name

    def pre_execute(self) -> None:
        self.printer.println(f"Dispatching workflow '{self.workflow_name}' in organization repo '{self.repo_name}':")

    async def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id

        self.printer.println(f"\nOrganization {style(org_config.name, bright=True)}[id={github_id}]")
        self.printer.level_up()

        try:
            try:
                credentials = self.config.get_credentials(org_config, only_token=True)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{str(e)}")
                return 1

            with GitHubProvider(credentials) as provider:
                success = await provider.dispatch_workflow(github_id, self.repo_name, self.workflow_name)
                if success is True:
                    self.printer.println(f"workflow '{self.workflow_name}' dispatched for repo '{self.repo_name}'")
                else:
                    self.printer.println(
                        f"failed to dispatch workflow '{self.workflow_name}' for repo '{self.repo_name}'"
                    )

            return 0
        finally:
            self.printer.level_down()
