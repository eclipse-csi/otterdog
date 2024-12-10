#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass
from functools import cached_property

import aiofiles
from slugify import slugify

from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import jsonnet_evaluate_file, query_json
from otterdog.webapp.blueprints.append_configuration import AppendConfigurationBlueprint
from otterdog.webapp.db.models import ConfigurationModel
from otterdog.webapp.tasks.blueprints import BlueprintTask, CheckResult


@dataclass(repr=False)
class AppendConfigurationTask(BlueprintTask):
    installation_id: int
    org_id: str
    repo_name: str
    blueprint: AppendConfigurationBlueprint
    config_model: ConfigurationModel

    @cached_property
    def github_organization_configuration(self) -> GitHubOrganization:
        return GitHubOrganization.from_model_data(self.config_model.config)

    async def _execute(self) -> CheckResult:
        self.logger.info(
            "checking configuration for blueprint '%s' in repo '%s/%s'",
            self.blueprint.id,
            self.org_id,
            self.repo_name,
        )

        result = CheckResult(remediation_needed=False)

        try:
            # evaluate the condition:
            # - true: the snippet should be added
            # - false: nothing to be done
            # - else: report a failure, the condition did not produce a boolean result
            query_result = query_json(self.blueprint.condition, self.config_model.config)
            if query_result is False:
                return result
            elif query_result is True:
                # condition succeeded, so we need to remediate
                pass
            else:
                # something unexpected happened when checking the condition
                # result is not a boolean
                self.logger.error(
                    "checking condition of blueprint '%s' for repo '%s/%s' resulting in: %s",
                    self.blueprint.id,
                    self.org_id,
                    self.repo_name,
                    query_result,
                )
                result.check_failed = True
                return result
        except RuntimeError as ex:
            self.logger.error(
                "error while checking for condition of blueprint '%s' in repo '%s/%s'",
                self.blueprint.id,
                self.org_id,
                self.repo_name,
                exc_info=ex,
            )
            result.check_failed = True
            return result

        await self._process_blueprint(result)
        return result

    def _render_configuration_snippet(self, snippet: str) -> str:
        import chevron

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

        return chevron.render(snippet, context)

    async def _process_blueprint(self, result: CheckResult) -> None:
        result.remediation_needed = True

        async with self.get_organization_config() as org_config:
            rest_api = await self.rest_api

            default_branch = await rest_api.repo.get_default_branch(self.org_id, self.repo_name)
            await self._create_branch_if_needed(default_branch)

            config_path = f"otterdog/{self.org_id}.jsonnet"
            current_configuration = await rest_api.content.get_content(self.org_id, self.repo_name, config_path)

            patched_configuration = (
                current_configuration.rstrip() + " + " + self._render_configuration_snippet(self.blueprint.content)
            )
            patched_config_file = org_config.jsonnet_config.org_config_file + "-PATCH"

            async with aiofiles.open(patched_config_file, "w") as file:
                await file.write(patched_configuration)

            try:
                jsonnet_evaluate_file(patched_config_file)
            except RuntimeError as ex:
                self.logger.error("failed to evaluate patched configuration", exc_info=ex)
                result.check_failed = True
                return

            # update content in the branch if necessary
            await rest_api.content.update_content(
                self.org_id,
                self.repo_name,
                config_path,
                patched_configuration,
                self.branch_name,
                "Updating configuration",
            )

        existing_pr_number = await self._find_existing_pull_request(default_branch)
        if existing_pr_number is not None:
            result.remediation_pr = existing_pr_number
            return

        pr_title = f"chore(otterdog): updating configuration due to blueprint `{self.blueprint.id}`"

        reviewers = [slugify(self._render_configuration_snippet(r)) for r in self.blueprint.reviewers]
        result.remediation_pr = await self._create_pull_request(pr_title, default_branch, reviewers)

    def __repr__(self) -> str:
        return f"AppendConfigurationTask(repo='{self.org_id}/{self.repo_name}', blueprint='{self.blueprint.id}')"
