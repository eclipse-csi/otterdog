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
from otterdog.models.environment_secret import EnvironmentSecret
from otterdog.models.environment_variable import EnvironmentVariable
from otterdog.utils import UNSET, Change, query_json

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

        # Variables and secrets are properly loaded with expected values
        assert any(v.name == "TEST_VAR" and v.value == "test_value" for v in env.variables)
        assert any(s.name == "TEST_SECRET" and s.value == "pass:path/to/secret" for s in env.secrets)
        # ensure the TEST_SECRET is not redacted
        test_secret = next((s for s in env.secrets if s.name == "TEST_SECRET"), None)
        assert test_secret is not None and not test_secret.has_dummy_secret()

    def test_secret_redaction_behavior(self):
        """Test that secrets with redacted values are properly handled"""
        # Secret with redacted value should be detected as dummy
        env_data = self.model_data.copy()
        env_data["secrets"] = [{"name": "REDACTED_SECRET", "value": "********"}]
        env = Environment.from_model_data(env_data)

        assert len(env.secrets) == 1
        assert env.secrets[0].has_dummy_secret()

    def test_add_retrieve_environment_variables(self):
        """Test that variables and secrets can be added/retrieved from environment"""
        # Start from JSON, then extend JSON to add a variable and reload
        env = Environment.from_model_data(self.model_data)

        # Test getter methods work
        assert env.get_variable("TEST_VAR") is not None
        assert env.get_variable("TEST_VAR").value == "test_value"
        assert env.get_secret("TEST_SECRET") is not None
        assert env.get_secret("TEST_SECRET").value == "pass:path/to/secret"

        # Add a variable via JSON to keep tests black-box
        extended = self.model_data.copy()
        extended_vars = [*list(extended.get("variables", [])), {"name": "NEW_VAR", "value": "new"}]
        extended["variables"] = extended_vars
        env2 = Environment.from_model_data(extended)
        assert env2.get_variable("NEW_VAR") is not None

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

    async def test_to_provider_with_variables_and_secrets(self):
        """Test converting environment with variables and secrets to provider data"""
        env = Environment.from_model_data(self.model_data)

        # Variables and secrets are nested models, should not appear in top-level provider_data
        provider_data = await env.to_provider_data(self.org_id, self.provider)

        # They should be handled separately via get_model_objects
        assert "variables" not in provider_data
        assert "secrets" not in provider_data

    def test_patch_from_json(self):
        """Test get_patch_to - comparing two Environment instances"""
        current = Environment.from_model_data(self.model_data)
        default = Environment.from_model_data(self.model_data)

        default.wait_timer = 30

        patch = current.get_patch_to(default)

        assert len(patch) >= 1
        assert patch["wait_timer"] == current.wait_timer

    def test_difference_from_json(self):
        """Test get_difference_from - finding differences between two instances"""
        current = Environment.from_model_data(self.model_data)
        other = Environment.from_model_data(self.model_data)

        other.wait_timer = 30

        diff = current.get_difference_from(other)

        assert len(diff) >= 1
        assert diff["wait_timer"] == Change(other.wait_timer, current.wait_timer)

    def test_environment_with_multiple_variables(self):
        """Test environment with multiple variables"""
        env_data = self.model_data.copy()
        env_data["variables"] = [
            {"name": "VAR_1", "value": "value1"},
            {"name": "VAR_2", "value": "value2"},
            {"name": "VAR_3", "value": "value3"},
        ]

        env = Environment.from_model_data(env_data)

        assert len(env.variables) == 3
        assert env.get_variable("VAR_1").value == "value1"
        assert env.get_variable("VAR_2").value == "value2"
        assert env.get_variable("VAR_3").value == "value3"

    def test_environment_with_multiple_secrets(self):
        """Test environment with multiple secrets"""
        env_data = self.model_data.copy()
        env_data["secrets"] = [
            {"name": "SECRET_1", "value": "pass:path/to/secret1"},
            {"name": "SECRET_2", "value": "bitwarden:id1@field"},
            {"name": "SECRET_3", "value": "pass:path/to/secret3"},
        ]

        env = Environment.from_model_data(env_data)

        assert len(env.secrets) == 3
        assert env.get_secret("SECRET_1").value == "pass:path/to/secret1"
        assert env.get_secret("SECRET_2").value == "bitwarden:id1@field"
        assert env.get_secret("SECRET_3").value == "pass:path/to/secret3"

    def test_github_environment_with_no_variables_or_secrets(self):
        """Test loading environment from GitHub that has no variables or secrets"""
        provider_data = self.load_json_resource("github-environment.json")

        env = Environment.from_provider_data(self.org_id, provider_data)

        assert env.name == "linux"
        assert env.variables == []
        assert env.secrets == []

    def test_environment_get_model_objects(self):
        """Test get_model_objects includes variables and secrets for processing"""
        env = Environment.from_model_data(self.model_data)

        model_objects = list(env.get_model_objects())

        # Should include both variable and secret
        assert len(model_objects) >= 2
        # Variables and secrets should be in the results
        object_types = [type(obj[0]).__name__ for obj in model_objects]
        assert "EnvironmentSecret" in object_types
        assert "EnvironmentVariable" in object_types

    # Note: nested variable/secret diffs are handled via nested model processing
    # (see get_model_objects test) rather than environment-level diff keys.

    def test_set_variables_replaces_list(self):
        """Test that set_variables replaces the entire list"""
        env = Environment.from_model_data(self.model_data)

        original_count = len(env.variables)
        assert original_count >= 1

        new_vars = [
            EnvironmentVariable.from_model_data({"name": "NEW_VAR_1", "value": "val1"}),
            EnvironmentVariable.from_model_data({"name": "NEW_VAR_2", "value": "val2"}),
        ]

        env.set_variables(new_vars)

        assert len(env.variables) == 2
        assert env.get_variable("NEW_VAR_1") is not None
        assert env.get_variable("TEST_VAR") is None

    def test_set_secrets_replaces_list(self):
        """Test that set_secrets replaces the entire list"""
        env = Environment.from_model_data(self.model_data)

        original_count = len(env.secrets)
        assert original_count >= 1

        new_secrets = [
            EnvironmentSecret.from_model_data({"name": "NEW_SEC_1", "value": "pass:p1"}),
            EnvironmentSecret.from_model_data({"name": "NEW_SEC_2", "value": "pass:p2"}),
        ]

        env.set_secrets(new_secrets)

        assert len(env.secrets) == 2
        assert env.get_secret("NEW_SEC_1") is not None
        assert env.get_secret("TEST_SECRET") is None

    def test_environment_variables_not_found(self):
        """Test retrieving non-existent variable returns None"""
        env = Environment.from_model_data(self.model_data)

        assert env.get_variable("NONEXISTENT") is None
        assert env.get_secret("NONEXISTENT") is None

    async def test_from_to_github_with_variables_and_secrets(self):
        """Test environment roundtrip includes variables and secrets"""
        # Create environment with variables and secrets
        env_data = self.model_data.copy()
        env_data["variables"] = [{"name": "VAR", "value": "val"}]
        env_data["secrets"] = [{"name": "SEC", "value": "pass:sec"}]

        env = Environment.from_model_data(env_data)

        # Convert to GitHub format
        provider_data = await env.to_provider_data(self.org_id, self.provider)

        # Variables and secrets are handled separately
        assert "variables" not in provider_data
        assert "secrets" not in provider_data

        # But the environment itself should be convertible
        assert provider_data["wait_timer"] == 15
