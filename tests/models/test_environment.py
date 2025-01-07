#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from collections.abc import Mapping
from typing import Any

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import ModelObject
from otterdog.models.environment import Environment
from otterdog.utils import UNSET, query_json

from . import ModelTest


class EnvironmentTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return Environment.from_model_data(data)

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_environment

    @property
    def model_data(self):
        return self.load_json_resource("otterdog-environment.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-environment.json")

    def test_load_from_model(self):
        env = Environment.from_model_data(self.model_data)

        assert env.id is UNSET
        assert env.node_id is UNSET
        assert env.name == "linux"
        assert env.wait_timer == 15
        assert env.reviewers == ["@netomi", "@OtterdogTest/eclipsefdn-security"]
        assert env.deployment_branch_policy == "selected"
        assert env.branch_policies == ["main", "develop/*"]

    def test_load_from_provider(self):
        env = Environment.from_provider_data(self.org_id, self.provider_data)

        assert env.id == 1102681190
        assert env.node_id == "EN_kwDOI9xAhM5BuZRm"
        assert env.name == "linux"
        assert env.wait_timer == 15
        assert env.reviewers == ["@netomi", "@OtterdogTest/eclipsefdn-security"]
        assert env.deployment_branch_policy == "selected"
        assert env.branch_policies == ["main", "develop/*"]

    async def test_to_provider(self):
        env = Environment.from_model_data(self.model_data)

        provider_data = await env.to_provider_data(self.org_id, self.provider)

        assert len(provider_data) == 5
        assert provider_data["wait_timer"] == 15

        assert query_json("reviewers[0].id", provider_data) == "id_netomi"
        assert query_json("reviewers[1].id", provider_data) == "id_OtterdogTest/eclipsefdn-security"

        assert query_json("deployment_branch_policy.protected_branches", provider_data) is False
        assert query_json("deployment_branch_policy.custom_branch_policies", provider_data) is True
