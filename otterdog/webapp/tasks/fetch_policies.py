#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass

from otterdog.providers.github.rest import RestApi
from otterdog.utils import print_error
from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.db.service import (
    cleanup_policies_of_owner,
    update_or_create_policy,
)
from otterdog.webapp.policies import Policy, PolicyType
from otterdog.webapp.tasks import InstallationBasedTask, Task


@dataclass(repr=False)
class FetchPoliciesTask(InstallationBasedTask, Task[None]):
    installation_id: int
    org_id: str
    repo_name: str
    global_policies: list[Policy]

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
        )

    async def _execute(self) -> None:
        self.logger.info(
            "fetching policies repo '%s/%s'",
            self.org_id,
            self.repo_name,
        )

        async with self.get_organization_config() as org_config:
            rest_api = await self.rest_api

            policies = await fetch_policies(rest_api, self.org_id, org_config.config_repo, self.global_policies)

            valid_types = [x.value for x in policies]
            await cleanup_policies_of_owner(self.org_id, valid_types)

            for policy in list(policies.values()):
                await update_or_create_policy(self.org_id, policy)

    def __repr__(self) -> str:
        return f"FetchPoliciesTask(repo='{self.org_id}/{self.repo_name}')"


async def fetch_policies(
    rest_api: RestApi, org_id: str, repo: str, global_policies: list[Policy]
) -> dict[PolicyType, Policy]:
    import yaml

    from otterdog.webapp.policies import read_policy

    config_file_path = "otterdog/policies"
    policies = {p.policy_type(): p for p in global_policies}
    try:
        entries = await rest_api.content.get_content_object(org_id, repo, config_file_path)
    except RuntimeError:
        entries = []

    for entry in entries:
        path = entry["path"]
        if path.endswith((".yml", "yaml")):
            content = await rest_api.content.get_content(org_id, repo, path)
            try:
                policy = read_policy(yaml.safe_load(content))
                policies[policy.policy_type()] = policy
            except RuntimeError as ex:
                print_error(f"failed reading policy from path '{path}': {ex!s}")

    return policies
