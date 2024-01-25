#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os

from otterdog.config import OrganizationConfig
from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import sort_jsonnet, strip_trailing_commas, style

from ..models import PatchContext
from . import Operation


class CanonicalDiffOperation(Operation):
    """
    Performs a canonical diff for organization configurations, i.e. comparing the current configuration
    with a canonical version and showing the unified diff of it.
    """

    def __init__(self):
        super().__init__()

    def pre_execute(self) -> None:
        self.printer.println("Showing canonical diff:")

    async def execute(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        jsonnet_config.init_template()

        self.printer.println(f"\nOrganization {style(org_config.name, bright=True)}[id={github_id}]")

        org_file_name = jsonnet_config.org_config_file

        if not os.path.exists(org_file_name):
            self.printer.print_error(
                f"configuration file '{org_file_name}' does not yet exist, run fetch-config or import first."
            )
            return 1

        try:
            organization = GitHubOrganization.load_from_file(github_id, org_file_name, self.config)
        except RuntimeError as ex:
            self.printer.print_error(f"failed to load configuration: {str(ex)}")
            return 1

        with open(org_file_name, "r") as file:
            original_config = file.read()

        original_config_without_comments: list[str] = strip_trailing_commas(
            sort_jsonnet(list(filter(lambda x: not x.strip().startswith("#"), original_config.split("\n"))))
        )

        context = PatchContext(github_id, organization.settings)
        canonical_config = organization.to_jsonnet(jsonnet_config, context)
        canonical_config_as_lines = strip_trailing_commas(sort_jsonnet(canonical_config.split("\n")))

        self.printer.println()

        for line in self._diff(canonical_config_as_lines, original_config_without_comments, "canonical", "original"):
            if line.startswith("+"):
                self.printer.println(style(line, fg="green"))
            elif line.startswith("-"):
                self.printer.println(style(line, fg="red"))
            else:
                self.printer.println(line)

        return 0

    @staticmethod
    def _diff(a, b, name_a, name_b):
        from subprocess import PIPE, Popen
        from tempfile import NamedTemporaryFile

        with NamedTemporaryFile() as file:
            file.write(bytes("\n".join(a), "utf-8"))
            file.flush()
            p = Popen(
                ["diff", "--label", name_a, "--label", name_b, "-u", "-w", "-", file.name], stdin=PIPE, stdout=PIPE
            )
            out, err = p.communicate(bytes("\n".join(b), "utf-8"))

            for line in out.decode("utf-8").split("\n"):
                yield line
