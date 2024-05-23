#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass

from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import jsonnet_evaluate_file
from otterdog.webapp.db.models import ConfigurationModel, StatisticsModel, TaskModel
from otterdog.webapp.db.service import save_config, save_statistics
from otterdog.webapp.tasks import InstallationBasedTask, Task
from otterdog.webapp.utils import fetch_config_from_github


@dataclass(repr=False)
class FetchConfigTask(InstallationBasedTask, Task[None]):
    installation_id: int
    org_id: str
    repo_name: str

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
        )

    async def _execute(self) -> None:
        self.logger.info(
            "fetching latest config from repo '%s/%s'",
            self.org_id,
            self.repo_name,
        )

        async with self.get_organization_config() as org_config:
            rest_api = await self.rest_api

            config_file = org_config.jsonnet_config.org_config_file
            sha = await fetch_config_from_github(
                rest_api,
                self.org_id,
                self.org_id,
                org_config.config_repo,
                config_file,
            )

            # save configuration
            config_data = jsonnet_evaluate_file(config_file)
            config = ConfigurationModel(  # type: ignore
                github_id=self.org_id,
                project_name=org_config.name,
                config=config_data,
                sha=sha,
            )
            await save_config(config)

            # save statistics
            github_organization = GitHubOrganization.from_model_data(config_data)

            archived_repos = 0
            repos_with_branch_protections = 0
            repos_with_secret_scanning = 0
            repos_with_secret_scanning_push_protection = 0
            repos_with_dependabot_alerts = 0
            repos_with_dependabot_security_updates = 0
            repos_with_private_vulnerability_reporting = 0

            for repo in github_organization.repositories:
                if repo.archived is True:
                    archived_repos += 1
                    continue

                if repo.private_vulnerability_reporting_enabled is True:
                    repos_with_private_vulnerability_reporting += 1

                if repo.dependabot_security_updates_enabled is True:
                    repos_with_dependabot_security_updates += 1
                elif repo.dependabot_alerts_enabled is True:
                    repos_with_dependabot_alerts += 1

                if len(repo.branch_protection_rules) > 0 or len(repo.rulesets) > 0:
                    repos_with_branch_protections += 1

                if repo.secret_scanning_push_protection == "enabled":
                    repos_with_secret_scanning_push_protection += 1
                elif repo.secret_scanning == "enabled":
                    repos_with_secret_scanning += 1

            statistics = StatisticsModel(  # type: ignore
                project_name=org_config.name,
                github_id=self.org_id,
                two_factor_enforced=1 if github_organization.settings.two_factor_requirement is True else 0,
                total_repos=len(github_organization.repositories),
                archived_repos=archived_repos,
                repos_with_branch_protection=repos_with_branch_protections,
                repos_with_private_vulnerability_reporting=repos_with_private_vulnerability_reporting,
                repos_with_secret_scanning=repos_with_secret_scanning,
                repos_with_secret_scanning_push_protection=repos_with_secret_scanning_push_protection,
                repos_with_dependabot_alerts=repos_with_dependabot_alerts,
                repos_with_dependabot_security_updates=repos_with_dependabot_security_updates,
            )
            await save_statistics(statistics)

    def __repr__(self) -> str:
        return f"FetchConfigTask(repo='{self.org_id}/{self.repo_name}')"
