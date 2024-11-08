#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import dataclass

import yaml

from otterdog.providers.github.rest import RestApi
from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.db.service import (
    cleanup_policies_of_owner,
    cleanup_policies_status_of_owner,
    update_or_create_policy,
)
from otterdog.webapp.policies import Policy, PolicyType, read_policy
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

            policies = await self._fetch_policies(rest_api, self.org_id, org_config.config_repo, self.global_policies)

            valid_types = [x.value for x in policies]
            await cleanup_policies_of_owner(self.org_id, valid_types)
            await cleanup_policies_status_of_owner(self.org_id, valid_types)

            for policy in list(policies.values()):
                await update_or_create_policy(self.org_id, policy)

    async def _fetch_policies(
        self,
        rest_api: RestApi,
        org_id: str,
        repo: str,
        global_policies: list[Policy],
    ) -> dict[PolicyType, Policy]:
        config_file_path = "otterdog/policies"
        policies = {p.type: p for p in global_policies}
        try:
            entries = await rest_api.content.get_content_object(org_id, repo, config_file_path)
        except RuntimeError:
            entries = []

        for entry in entries:
            path = entry["path"]
            if path.endswith((".yml", "yaml")):
                content = await rest_api.content.get_content(org_id, repo, path)
                try:
                    # TODO: do not hardcode the path to the default branch
                    policy_path = f"https://github.com/{org_id}/{repo}/blob/main/{path}"
                    policy = read_policy(policy_path, yaml.safe_load(content))

                    if policy.type in policies:
                        global_policy = policies[policy.type]
                        policy = global_policy.merge(policy)

                    policies[policy.type] = policy
                except (ValueError, RuntimeError) as ex:
                    self.logger.error(f"failed reading policy from path '{path}'", exc_info=ex)

        return policies

    def __repr__(self) -> str:
        return f"FetchPoliciesTask(repo='{self.org_id}/{self.repo_name}')"
