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
from otterdog.models.environment_secret import EnvironmentSecret
from otterdog.utils import Change

from . import ModelTest


class EnvironmentSecretTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return EnvironmentSecret.from_model_data(data)

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_environment_secret

    @property
    def model_data(self):
        return self.load_json_resource("otterdog-environment-secret.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-environment-secret.json")

    def test_load_from_model(self):
        secret = EnvironmentSecret.from_model_data(self.model_data)

        assert secret.name == "ENV-SECRET"
        assert secret.value == "1234"

    def test_load_from_provider(self):
        secret = EnvironmentSecret.from_provider_data(self.org_id, self.provider_data)

        assert secret.name == "ENV-SECRET"
        assert secret.value == "********"

    def test_patch(self):
        current = EnvironmentSecret.from_model_data(self.model_data)
        default = EnvironmentSecret.from_model_data(self.model_data)

        default.value = "5678"

        patch = current.get_patch_to(default)

        assert len(patch) == 1
        assert patch["value"] == current.value

    def test_difference(self):
        current = EnvironmentSecret.from_model_data(self.model_data)
        other = EnvironmentSecret.from_model_data(self.model_data)

        other.value = "5678"

        diff = current.get_difference_from(other)

        assert len(diff) == 1
        assert diff["value"] == Change(other.value, current.value)
