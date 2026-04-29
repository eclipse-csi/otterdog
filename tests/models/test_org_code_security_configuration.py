#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from collections.abc import Mapping
from typing import Any

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import ModelObject
from otterdog.models.organization_code_security_configuration import (
    OrganizationCodeSecurityConfiguration,
)
from otterdog.utils import UNSET

from . import ModelTest


class OrganizationCodeSecurityConfigurationTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return OrganizationCodeSecurityConfiguration.from_model_data(data)

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_org_code_security_configuration

    @property
    def model_data(self):
        return self.load_json_resource("otterdog-org-code-security-configuration.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-org-code-security-configuration.json")

    def test_load_from_model(self):
        configuration = OrganizationCodeSecurityConfiguration.from_model_data(self.model_data)

        assert configuration.id is UNSET
        assert configuration.name == "my-config"
        assert configuration.description == "My code security configuration"
        assert configuration.advanced_security == "enabled"
        assert configuration.dependency_graph == "enabled"
        assert configuration.dependency_graph_autosubmit_action == "enabled"
        assert configuration.dependabot_alerts == "enabled"
        assert configuration.dependabot_security_updates == "enabled"
        assert configuration.code_scanning_default_setup == "enabled"
        assert configuration.secret_scanning == "enabled"
        assert configuration.secret_scanning_push_protection == "enabled"
        assert configuration.secret_scanning_delegated_bypass == "disabled"
        assert configuration.secret_scanning_validity_checks == "enabled"
        assert configuration.secret_scanning_non_provider_patterns == "enabled"
        assert configuration.private_vulnerability_reporting == "enabled"
        assert configuration.enforcement == "enforced"

    def test_load_from_provider(self):
        configuration = OrganizationCodeSecurityConfiguration.from_provider_data(self.org_id, self.provider_data)

        assert configuration.id == 42
        assert configuration.name == "my-config"
        assert configuration.description == "My code security configuration"
        assert configuration.advanced_security == "enabled"
        assert configuration.enforcement == "enforced"

    async def test_to_provider(self):
        configuration = OrganizationCodeSecurityConfiguration.from_model_data(self.model_data)

        provider_data = await configuration.to_provider_data(self.org_id, self.provider)

        assert "id" not in provider_data
        assert provider_data["name"] == "my-config"
        assert provider_data["advanced_security"] == "enabled"
        assert provider_data["enforcement"] == "enforced"
