#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from collections import Counter
from dataclasses import dataclass

import aiofiles

from otterdog.models import CostPolicy
from otterdog.models.github_organization import GitHubOrganization
from otterdog.models.repository import Repository
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

            # save configuration — confine imports to the org config directory,
            # matching the layout expected by org configs (vendored templates only).
            config_data = jsonnet_evaluate_file(config_file, import_base_dir=org_config.jsonnet_config.org_dir)
            async with aiofiles.open(config_file) as file:
                config_jsonnet = await file.read()
            branch = await rest_api.repo.get_default_branch(self.org_id, org_config.config_repo)

            config = ConfigurationModel(  # type: ignore
                github_id=self.org_id,
                project_name=org_config.name,
                config=config_data,
                sha=sha,
                jsonnet=config_jsonnet,
                branch=branch,
            )
            await save_config(config)

            # save statistics
            github_organization = GitHubOrganization.from_model_data(config_data)
            statistics = get_organization_statistics(org_config.name, self.org_id, github_organization)
            await save_statistics(statistics)

    def __repr__(self) -> str:
        return f"FetchConfigTask(repo='{self.org_id}/{self.repo_name}')"


# the statistics counting the active repositories, see _get_repository_statistics
_REPOSITORY_STATISTICS = [
    "repos_with_branch_protection",
    "repos_with_private_vulnerability_reporting",
    "repos_with_secret_scanning",
    "repos_with_secret_scanning_push_protection",
    "repos_with_dependabot_alerts",
    "repos_with_dependabot_security_updates",
    "repos_with_code_scanning",
    "repos_with_code_security_configuration",
    "private_repos_with_licensed_security_features",
]


def get_organization_statistics(
    project_name: str, github_id: str, github_organization: GitHubOrganization
) -> StatisticsModel:
    """Returns the statistics of an organization, with the security settings that apply to its repositories."""
    counts: Counter[str] = Counter()
    for repo in github_organization.repositories:
        if repo.archived is True:
            counts["archived_repos"] += 1
        else:
            counts.update(_get_repository_statistics(github_organization, repo))

    return StatisticsModel(  # type: ignore
        project_name=project_name,
        github_id=github_id,
        two_factor_enforced=1 if github_organization.settings.two_factor_requirement is True else 0,
        total_repos=len(github_organization.repositories),
        archived_repos=counts["archived_repos"],
        **{name: counts[name] for name in _REPOSITORY_STATISTICS},
    )


def _get_repository_statistics(github_organization: GitHubOrganization, configured_repo: Repository) -> list[str]:
    """Returns the statistics an active repository counts for."""
    # the settings that the code security configuration of the repository sets take precedence
    repo = github_organization.get_effective_repository(configured_repo)
    configuration = github_organization.get_attached_code_security_configuration(repo)

    statistics = []
    if configuration is not None:
        statistics.append("repos_with_code_security_configuration")
        # Code Security and Secret Protection are licensed for private repositories
        if repo.private is True and configuration.is_cost_related(CostPolicy()):
            statistics.append("private_repos_with_licensed_security_features")

    if repo.code_scanning_default_setup_enabled is True:
        statistics.append("repos_with_code_scanning")

    if repo.private_vulnerability_reporting_enabled is True:
        statistics.append("repos_with_private_vulnerability_reporting")

    if repo.dependabot_security_updates_enabled is True:
        statistics.append("repos_with_dependabot_security_updates")
    elif repo.dependabot_alerts_enabled is True:
        statistics.append("repos_with_dependabot_alerts")

    if len(repo.branch_protection_rules) > 0 or len(repo.rulesets) > 0:
        statistics.append("repos_with_branch_protection")

    if repo.secret_scanning_push_protection == "enabled":
        statistics.append("repos_with_secret_scanning_push_protection")
    elif repo.secret_scanning == "enabled":
        statistics.append("repos_with_secret_scanning")

    return statistics
