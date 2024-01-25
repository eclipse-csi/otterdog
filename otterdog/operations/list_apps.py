#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from typing import Any

from otterdog.config import OrganizationConfig
from otterdog.providers.github import GitHubProvider
from otterdog.utils import is_info_enabled, style

from . import Operation


class ListAppsOperation(Operation):
    """
    Lists installed GitHub apps for an organization.
    """

    def __init__(self, json_output: bool):
        super().__init__()
        self.all_apps: dict[str, Any] = {}
        self.json_output = json_output

    def pre_execute(self) -> None:
        if not self.json_output or is_info_enabled():
            self.printer.println("Listing app installations:")

    def post_execute(self) -> None:
        if self.json_output is True:
            if is_info_enabled():
                self.printer.println()
            apps = [v for k, v in sorted(self.all_apps.items())]
            self.printer.println(json.dumps(apps, indent=2))

    async def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id

        if not self.json_output or is_info_enabled():
            self.printer.println(f"\nOrganization {style(org_config.name, bright=True)}[id={github_id}]")
            self.printer.level_up()

        try:
            try:
                credentials = self.config.get_credentials(org_config, only_token=True)
            except RuntimeError as e:
                self.printer.print_error(f"invalid credentials\n{str(e)}")
                return 1

            with GitHubProvider(credentials) as provider:
                apps = await provider.rest_api.org.get_app_installations(github_id)

            if not self.json_output:
                for app in apps:
                    filtered = {key: app[key] for key in ["app_id", "permissions"]}
                    self.printer.println()
                    self.print_dict(filtered, f"app['{app['app_slug']}']", "", "black")
            else:
                if is_info_enabled():
                    self.printer.println(f"Found {len(apps)} app installations.")

                for app in apps:
                    app_slug = str(app["app_slug"])
                    filtered = {key: app[key] for key in ["app_id", "app_slug", "permissions"]}
                    self.all_apps[app_slug] = filtered

            return 0
        finally:
            if not self.json_output or is_info_enabled():
                self.printer.level_down()
