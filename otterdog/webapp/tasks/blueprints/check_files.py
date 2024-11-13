#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass

from otterdog.webapp.blueprints.required_file import RequiredFile, RequiredFileBlueprint
from otterdog.webapp.tasks.blueprints import BlueprintTask, CheckResult


@dataclass(repr=False)
class CheckFilesTask(BlueprintTask):
    installation_id: int
    org_id: str
    repo_name: str
    blueprint: RequiredFileBlueprint

    async def _execute(self) -> CheckResult:
        self.logger.info(
            "checking files for blueprint '%s' in repo '%s/%s'",
            self.blueprint.id,
            self.org_id,
            self.repo_name,
        )

        result = CheckResult(remediation_needed=False)
        rest_api = await self.rest_api

        try:
            await rest_api.content.get_contents(self.org_id, self.repo_name, ".")
        except RuntimeError:
            # if no content exists, the repo is still empty, skip processing
            result.check_failed = True
            return result

        files_needing_update = []
        for file in self.blueprint.files:
            try:
                content = await rest_api.content.get_content(self.org_id, self.repo_name, file.path)
                if file.strict is False or file.content == content:
                    continue
            except RuntimeError:
                # file does not exist, so let's create it
                pass

            files_needing_update.append(file)

        if len(files_needing_update) > 0:
            self.logger.debug(
                f"creating pull request due to blueprint '{self.blueprint.id}' in repo '{self.org_id}/{self.repo_name}'"
            )
            await self._process_files(files_needing_update, result)

        return result

    async def _process_files(
        self,
        files_needing_update: list[RequiredFile],
        result: CheckResult,
    ) -> None:
        result.remediation_needed = True

        rest_api = await self.rest_api
        default_branch = await rest_api.repo.get_default_branch(self.org_id, self.repo_name)

        await self._create_branch_if_needed(default_branch)

        # update content in the branch if necessary
        for file in files_needing_update:
            await rest_api.content.update_content(
                self.org_id,
                self.repo_name,
                file.path,
                file.content,
                self.branch_name,
                f"Updating file {file.path}",
            )

        existing_pr_number = await self._find_existing_pull_request(default_branch)
        if existing_pr_number is not None:
            result.remediation_pr = existing_pr_number
            return

        pr_title = f"chore(otterdog): adding / updating file(s) due to blueprint `{self.blueprint.id}`"
        result.remediation_pr = await self._create_pull_request(pr_title, default_branch)

    def __repr__(self) -> str:
        return f"CheckFilesTask(repo='{self.org_id}/{self.repo_name}', blueprint='{self.blueprint.id}')"
