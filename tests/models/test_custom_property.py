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
from otterdog.models.custom_property import CustomProperty
from otterdog.utils import Change

from . import ModelTest


class CustomPropertyTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return CustomProperty.from_model_data(data)

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_org_custom_property

    @property
    def model_data(self) -> Any:
        return {
            "name": "language",
            "value_type": "single_select",
            "required": True,
            "default_value": "Python",
            "description": "Primary language",
            "allowed_values": ["Python", "Java"],
        }

    @property
    def provider_data(self) -> Any:
        return {
            "property_name": "language",
            "value_type": "single_select",
            "required": True,
            "default_value": "Python",
            "description": "Primary language",
            "allowed_values": ["Python", "Java"],
        }

    def test_load_from_model(self):
        """Loads a custom property from model data."""
        custom_property = CustomProperty.from_model_data(self.model_data)

        assert custom_property.name == "language"
        assert custom_property.value_type == "single_select"
        assert custom_property.required is True
        assert custom_property.default_value == "Python"
        assert custom_property.description == "Primary language"
        assert custom_property.allowed_values == ["Python", "Java"]

    def test_load_from_provider(self):
        """Loads a custom property from provider data."""
        custom_property = CustomProperty.from_provider_data(self.org_id, self.provider_data)

        assert custom_property.name == "language"
        assert custom_property.value_type == "single_select"
        assert custom_property.required is True
        assert custom_property.default_value == "Python"
        assert custom_property.description == "Primary language"
        assert custom_property.allowed_values == ["Python", "Java"]

    async def test_to_provider_excludes_name(self):
        """Converts to provider data without including the name key."""
        custom_property = CustomProperty.from_model_data(self.model_data)

        provider_data = await custom_property.to_provider_data(self.org_id, self.provider)

        assert "name" not in provider_data
        assert provider_data["value_type"] == "single_select"
        assert provider_data["required"] is True
        assert provider_data["default_value"] == "Python"

    def test_patch_includes_default_value_when_not_required(self):
        """Includes default_value in patch output when it differs."""
        current = CustomProperty.from_model_data(
            {
                "name": "cost_center",
                "value_type": "string",
                "required": False,
                "default_value": "",
                "description": None,
                "allowed_values": None,
            }
        )
        other = CustomProperty.from_model_data(
            {
                "name": "cost_center",
                "value_type": "string",
                "required": False,
                "default_value": "should-be-ignored",
                "description": None,
                "allowed_values": None,
            }
        )

        patch = current.get_patch_to(other)

        assert len(patch) == 1
        assert patch["default_value"] == ""

    def test_difference_ignores_allowed_values_for_non_select_type(self):
        """Ignores allowed_values changes for non-select value types in diffs."""
        current = CustomProperty.from_model_data(
            {
                "name": "cost_center",
                "value_type": "string",
                "required": False,
                "default_value": "",
                "description": None,
                "allowed_values": ["A", "B"],
            }
        )
        other = CustomProperty.from_model_data(
            {
                "name": "cost_center",
                "value_type": "string",
                "required": False,
                "default_value": "",
                "description": None,
                "allowed_values": ["X", "Y", "Z"],
            }
        )

        diff = current.get_difference_from(other)

        assert diff == {}

    def test_difference_includes_default_value_when_required(self):
        """Includes required default_value changes in computed differences."""
        current = CustomProperty.from_model_data(self.model_data)
        other = CustomProperty.from_model_data(self.model_data)
        other.default_value = "Java"

        diff = current.get_difference_from(other)

        assert len(diff) == 1
        assert diff["default_value"] == Change("Java", "Python")
