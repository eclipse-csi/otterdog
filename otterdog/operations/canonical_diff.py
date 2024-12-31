#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from aiofiles import open, tempfile

from otterdog.models import PatchContext
from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import sort_jsonnet, strip_trailing_commas

from . import Operation

if TYPE_CHECKING:
    from otterdog.config import OrganizationConfig


class CanonicalDiffOperation(Operation):
    """
    Performs a canonical diff for organization configurations, i.e. comparing the current configuration
    with a canonical version and showing the unified diff of it.
    """

    def __init__(self):
        super().__init__()

    def pre_execute(self) -> None:
        self.printer.println("Showing canonical diff:")

    async def execute(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        await jsonnet_config.init_template()

        self._print_project_header(org_config, org_index, org_count)

        org_file_name = jsonnet_config.org_config_file
        if not await self.check_config_file_exists(org_file_name):
            return 1

        try:
            organization = GitHubOrganization.load_from_file(github_id, org_file_name)
        except RuntimeError as ex:
            self.printer.print_error(f"failed to load configuration: {ex!s}")
            return 1

        async with open(org_file_name) as file:
            original_config = await file.read()

        original_config_without_comments: list[str] = strip_trailing_commas(
            sort_jsonnet(list(filter(lambda x: not x.strip().startswith("#"), original_config.split("\n"))))
        )

        context = PatchContext(github_id, organization.settings)
        canonical_config = organization.to_jsonnet(jsonnet_config, context)
        canonical_config_as_lines = strip_trailing_commas(sort_jsonnet(canonical_config.split("\n")))

        self.printer.println()

        async for line in self._diff(
            canonical_config_as_lines, original_config_without_comments, "canonical", "original"
        ):
            if line.startswith("+"):
                self.printer.println(f"[green]{line}[/]")
            elif line.startswith("-"):
                self.printer.println(f"[red]{line}[/]")
            else:
                self.printer.println(line)

        return 0

    @staticmethod
    async def _diff(a, b, name_a, name_b):
        async with tempfile.NamedTemporaryFile() as file:
            await file.write(bytes("\n".join(a), "utf-8"))
            await file.flush()

            try:
                cmd = f"diff --label {name_a} --label {name_b} -u -w - {file.name}"
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                out, _ = await proc.communicate(bytes("\n".join(b), "utf-8"))

                for line in out.decode("utf-8").split("\n"):
                    yield line
            except BrokenPipeError as ex:
                raise RuntimeError(f"failed to run diff command: {ex!s}") from ex
