#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from otterdog.models.environment import Environment
from otterdog.utils import UNSET

from . import ModelTest


class EnvironmentTest(ModelTest):
    @property
    def model_data(self):
        return self.load_json_resource("otterdog-environment.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-environment.json")

    def test_load_from_model(self):
        pass
        env = Environment.from_model_data(self.model_data)

        assert env.id is UNSET
        assert env.node_id is UNSET
        assert env.name == "linux"
        assert env.wait_timer == 15
        assert env.reviewers == ["@netomi", "@OtterdogTest/eclipsefdn-security"]
        assert env.deployment_branch_policy == "pattern"
        assert env.branch_policies == ["main", "develop/*"]

    def test_load_from_provider(self):
        env = Environment.from_provider_data(self.org_id, self.provider_data)

        assert env.id == 1102681190
        assert env.node_id == "EN_kwDOI9xAhM5BuZRm"
        assert env.name == "linux"
        assert env.wait_timer == 15
        assert env.reviewers == ["@netomi", "@OtterdogTest/eclipsefdn-security"]
        assert env.deployment_branch_policy == "pattern"
        assert env.branch_policies == ["main", "develop/*"]
