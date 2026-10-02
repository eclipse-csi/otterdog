#  *******************************************************************************
#  Copyright (c) 2024-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass
from functools import cached_property

from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import render_chevron
from otterdog.webapp.blueprints.required_file import RequiredFile, RequiredFileBlueprint
from otterdog.webapp.db.models import ConfigurationModel
from otterdog.webapp.tasks.blueprints import BlueprintTask, CheckResult, RemediationFile


@dataclass(repr=False)
class CheckFilesTask(BlueprintTask):
    installation_id: int
    org_id: str
    repo_name: str
    blueprint: RequiredFileBlueprint
    config_model: ConfigurationModel

    @cached_property
    def github_organization_configuration(self) -> GitHubOrganization:
        return GitHubOrganization.from_model_data(self.config_model.config)

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
            file_content = self._render_content(file)

            try:
                content = await rest_api.content.get_content(self.org_id, self.repo_name, file.path)
                if file.strict is False or file_content == content:
                    continue
            except RuntimeError:
                # file does not exist, so let's create it
                pass

            files_needing_update.append((file, file_content))

        if len(files_needing_update) > 0:
            self.logger.debug(
                f"creating pull request due to blueprint '{self.blueprint.id}' in repo '{self.org_id}/{self.repo_name}'"
            )
            await self._process_files(files_needing_update, result)

        return result

    def _render_content(self, file: RequiredFile) -> str:
        context = {
            "project_name": self.config_model.project_name,
            "github_id": self.config_model.github_id,
            "repo_name": self.repo_name,
            "org": self.github_organization_configuration.settings,
            "repo": self.github_organization_configuration.get_repository(self.repo_name),
            "repo_url": f"https://github.com/{self.org_id}/{self.repo_name}",
            "blueprint_id": self.blueprint.id,
            "blueprint_url": self.blueprint.path,
        }

        return render_chevron(file.content, context)

    async def _process_files(
        self,
        files_needing_update: list[tuple[RequiredFile, str]],
        result: CheckResult,
    ) -> None:
        result.remediation_needed = True

        rest_api = await self.rest_api
        default_branch = await rest_api.repo.get_default_branch(self.org_id, self.repo_name)

        # True if the branch is new, was reset, or only carries otterdog commits
        branch_is_fresh = await self._prepare_branch(default_branch)

        remediation_files = []
        for file, content in files_needing_update:
            # if the branch carries commits of maintainers and the required file is not strict,
            # do not update the file content in the branch as it would override their modifications.
            write = file.strict is True or branch_is_fresh is True
            remediation_files.append(RemediationFile(file.path, file.strict, write))

            if write is False:
                continue

            await rest_api.content.update_content(
                self.org_id,
                self.repo_name,
                file.path,
                content,
                self.branch_name,
                f"Updating file {file.path}",
            )

        result.content_written = all(file.written for file in remediation_files)

        existing_pr_number = await self._find_existing_pull_request(default_branch)
        if existing_pr_number is not None:
            result.remediation_pr = existing_pr_number
            await self._update_existing_pull_request(existing_pr_number, remediation_files)
        else:
            pr_title = f"chore(otterdog): adding / updating file(s) due to blueprint `{self.blueprint.id}`"
            result.remediation_pr = await self._create_pull_request(pr_title, default_branch, files=remediation_files)

    def __repr__(self) -> str:
        return f"CheckFilesTask(repo='{self.org_id}/{self.repo_name}', blueprint='{self.blueprint.id}')"
