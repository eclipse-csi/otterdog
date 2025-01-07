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
from otterdog.models.organization_secret import OrganizationSecret
from otterdog.utils import Change

from . import ModelTest


class OrganizationSecretTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return OrganizationSecret.from_model_data(data)

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_org_secret

    @property
    def model_data(self):
        return self.load_json_resource("otterdog-org-secret.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-org-secret.json")

    def test_load_from_model(self):
        secret = OrganizationSecret.from_model_data(self.model_data)

        assert secret.name == "TEST-SECRET"
        assert secret.visibility == "selected"
        assert secret.selected_repositories == ["test-repo"]
        assert secret.value == "1234"

    def test_load_from_provider(self):
        secret = OrganizationSecret.from_provider_data(self.org_id, self.provider_data)

        assert secret.name == "TEST-SECRET"
        assert secret.visibility == "selected"
        assert secret.selected_repositories == ["test-repo"]
        assert secret.value == "********"

    def test_patch(self):
        current = OrganizationSecret.from_model_data(self.model_data)
        default = OrganizationSecret.from_model_data(self.model_data)

        default.visibility = "public"

        patch = current.get_patch_to(default)

        assert len(patch) == 1
        assert patch["visibility"] == current.visibility

    def test_difference(self):
        current = OrganizationSecret.from_model_data(self.model_data)
        other = OrganizationSecret.from_model_data(self.model_data)

        other.visibility = "public"

        diff = current.get_difference_from(other)

        assert len(diff) == 1
        assert diff["visibility"] == Change(other.visibility, current.visibility)
