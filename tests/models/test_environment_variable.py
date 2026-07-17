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
from otterdog.models.environment_variable import EnvironmentVariable
from otterdog.utils import Change

from . import ModelTest


class EnvironmentVariableTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return EnvironmentVariable.from_model_data(data)

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_environment_variable

    @property
    def model_data(self):
        return self.load_json_resource("otterdog-environment-variable.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-environment-variable.json")

    def test_load_from_model(self):
        variable = EnvironmentVariable.from_model_data(self.model_data)

        assert variable.name == "ENV-VARIABLE"
        assert variable.value == "some-value"

    def test_load_from_provider(self):
        variable = EnvironmentVariable.from_provider_data(self.org_id, self.provider_data)

        assert variable.name == "ENV-VARIABLE"
        assert variable.value == "some-value"

    def test_patch(self):
        current = EnvironmentVariable.from_model_data(self.model_data)
        default = EnvironmentVariable.from_model_data(self.model_data)

        default.value = "other-value"

        patch = current.get_patch_to(default)

        assert len(patch) == 1
        assert patch["value"] == current.value

    def test_difference(self):
        current = EnvironmentVariable.from_model_data(self.model_data)
        other = EnvironmentVariable.from_model_data(self.model_data)

        other.value = "other-value"

        diff = current.get_difference_from(other)

        assert len(diff) == 1
        assert diff["value"] == Change(other.value, current.value)
