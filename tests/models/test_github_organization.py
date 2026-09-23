#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os
import unittest

import jsonschema

from otterdog.config import OtterdogConfig
from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import jsonnet_evaluate_file


class GitHubOrganizationTest(unittest.IsolatedAsyncioTestCase):
    TEST_ORG = "test-org"
    BASE_TEMPLATE_URL = "https://github.com/otterdog/test-defaults#test-defaults.libsonnet@main"

    async def asyncSetUp(self):
        base_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "resources")
        otterdog_config_file = os.path.join(base_dir, "otterdog.json")

        self.otterdog_config = OtterdogConfig.from_file(otterdog_config_file, True)
        self.org_config = self.otterdog_config.get_organization_config(self.TEST_ORG)
        self.jsonnet_config = self.org_config.jsonnet_config
        await self.jsonnet_config.init_template()

    def test_load_from_file(self):
        organization = GitHubOrganization.load_from_file(self.TEST_ORG, self.jsonnet_config.org_config_file)

        assert organization.github_id == "test-org"
        assert len(organization.webhooks) == 1
        assert len(organization.repositories) == 2

    def test_load_from_model_ignores_unknown_properties(self):
        data = jsonnet_evaluate_file(self.jsonnet_config.org_config_file)
        data["settings"]["unknown_property_xyz"] = True

        with self.assertLogs("otterdog.models.github_organization", level="WARNING") as log:
            organization = GitHubOrganization.from_model_data(data)

        assert organization.github_id == "test-org"
        assert any("unknown_property_xyz" in message for message in log.output)

    def test_load_from_model_still_rejects_invalid_properties(self):
        data = jsonnet_evaluate_file(self.jsonnet_config.org_config_file)
        data["settings"]["plan"] = 123

        with self.assertRaises(jsonschema.exceptions.ValidationError):
            GitHubOrganization.from_model_data(data)
