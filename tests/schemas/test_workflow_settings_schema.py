#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""Test schema composition for workflow-settings.json and its extensions."""

import json
from importlib.resources import as_file, files

import pytest
from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

import otterdog.resources as resources


class TestWorkflowSettingsSchemaComposition:
    """Test that workflow-settings.json properties are properly inherited."""

    @pytest.fixture
    def schemas_registry(self):
        """Create a registry for resolving schema references."""
        with as_file(files(resources).joinpath("schemas")) as resource_dir:

            def retrieve_from_filesystem(uri: str):
                path = resource_dir.joinpath(uri)
                if not path.exists():
                    raise NoSuchResource(ref=uri)

                contents = json.loads(path.read_text())
                return Resource.from_contents(contents)

            yield Registry(retrieve=retrieve_from_filesystem)

    @pytest.fixture
    def org_workflow_schema(self):
        """Load the org-workflow-settings.json schema."""
        schema_text = files(resources).joinpath("schemas/org-workflow-settings.json").read_text()
        return json.loads(schema_text)

    @pytest.fixture
    def repo_workflow_schema(self):
        """Load the repo-workflow-settings.json schema."""
        schema_text = files(resources).joinpath("schemas/repo-workflow-settings.json").read_text()
        return json.loads(schema_text)

    def test_org_workflow_settings_accepts_fork_pr_approval_policy(self, org_workflow_schema, schemas_registry):
        """Test that org-workflow-settings accepts fork_pr_approval_policy from base schema."""
        validator = Draft202012Validator(org_workflow_schema, registry=schemas_registry)

        data = {
            "actions_can_approve_pull_request_reviews": False,
            "allow_action_patterns": [],
            "allow_github_owned_actions": True,
            "allow_verified_creator_actions": True,
            "allowed_actions": "all",
            "default_workflow_permissions": "write",
            "enabled_repositories": "all",
            "fork_pr_approval_policy": "first_time_contributors_new_to_github",
            "selected_repositories": [],
        }

        validator.validate(data)

    def test_org_workflow_settings_accepts_all_base_properties(self, org_workflow_schema, schemas_registry):
        """Test that all base workflow-settings properties are accepted."""
        validator = Draft202012Validator(org_workflow_schema, registry=schemas_registry)

        data = {
            # Required org-specific field
            "enabled_repositories": "selected",
            "selected_repositories": ["repo1", "repo2"],
            # Base workflow-settings fields
            "allowed_actions": "selected",
            "allow_github_owned_actions": False,
            "allow_verified_creator_actions": False,
            "allow_action_patterns": ["org/*", "action@v*"],
            "default_workflow_permissions": "read",
            "actions_can_approve_pull_request_reviews": True,
            "fork_pr_approval_policy": "first_time_contributors",
        }

        validator.validate(data)

    def test_org_workflow_settings_rejects_unknown_properties(self, org_workflow_schema, schemas_registry):
        """Test that unknown properties are rejected due to unevaluatedProperties: false."""
        validator = Draft202012Validator(org_workflow_schema, registry=schemas_registry)

        data = {
            "enabled_repositories": "all",
            "unknown_property": "should_fail",
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(data)

        assert "unevaluatedProperties" in str(exc_info.value)
        assert "unknown_property" in str(exc_info.value)

    def test_repo_workflow_settings_accepts_fork_pr_approval_policy(self, repo_workflow_schema, schemas_registry):
        """Test that repo-workflow-settings accepts fork_pr_approval_policy from base schema."""
        validator = Draft202012Validator(repo_workflow_schema, registry=schemas_registry)

        data = {
            # Required repo-specific field
            "enabled": True,
            # Base workflow-settings fields
            "allowed_actions": "all",
            "allow_github_owned_actions": True,
            "allow_verified_creator_actions": True,
            "allow_action_patterns": [],
            "default_workflow_permissions": "write",
            "actions_can_approve_pull_request_reviews": False,
            "fork_pr_approval_policy": "all_external_contributors",
        }

        validator.validate(data)

    def test_repo_workflow_settings_accepts_all_base_properties(self, repo_workflow_schema, schemas_registry):
        """Test that all base workflow-settings properties are accepted."""
        validator = Draft202012Validator(repo_workflow_schema, registry=schemas_registry)

        data = {
            # Required repo-specific field
            "enabled": False,
            # Base workflow-settings fields
            "allowed_actions": "local_only",
            "allow_github_owned_actions": True,
            "allow_verified_creator_actions": False,
            "allow_action_patterns": ["my-org/*"],
            "default_workflow_permissions": "read",
            "actions_can_approve_pull_request_reviews": False,
            "fork_pr_approval_policy": "first_time_contributors_new_to_github",
        }

        validator.validate(data)

    def test_repo_workflow_settings_rejects_unknown_properties(self, repo_workflow_schema, schemas_registry):
        """Test that unknown properties are rejected."""
        validator = Draft202012Validator(repo_workflow_schema, registry=schemas_registry)

        data = {
            "enabled": True,
            "this_does_not_exist": "invalid",
        }

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(data)

        assert "unevaluatedProperties" in str(exc_info.value)
        assert "this_does_not_exist" in str(exc_info.value)

    @pytest.mark.parametrize(
        "field_name,field_value",
        [
            ("allowed_actions", "all"),
            ("allow_github_owned_actions", True),
            ("allow_verified_creator_actions", False),
            ("allow_action_patterns", ["pattern1", "pattern2"]),
            ("default_workflow_permissions", "write"),
            ("actions_can_approve_pull_request_reviews", True),
            ("fork_pr_approval_policy", "first_time_contributors"),
        ],
    )
    def test_org_workflow_inherits_individual_base_fields(
        self, org_workflow_schema, schemas_registry, field_name, field_value
    ):
        """Test that each base field is properly inherited in org-workflow-settings."""
        validator = Draft202012Validator(org_workflow_schema, registry=schemas_registry)

        data = {
            "enabled_repositories": "all",  # Required field
            field_name: field_value,
        }

        validator.validate(data)

    @pytest.mark.parametrize(
        "field_name,field_value",
        [
            ("allowed_actions", "selected"),
            ("allow_github_owned_actions", False),
            ("allow_verified_creator_actions", True),
            ("allow_action_patterns", []),
            ("default_workflow_permissions", "read"),
            ("actions_can_approve_pull_request_reviews", False),
            ("fork_pr_approval_policy", "all_external_contributors"),
        ],
    )
    def test_repo_workflow_inherits_individual_base_fields(
        self, repo_workflow_schema, schemas_registry, field_name, field_value
    ):
        """Test that each base field is properly inherited in repo-workflow-settings."""
        validator = Draft202012Validator(repo_workflow_schema, registry=schemas_registry)

        data = {
            "enabled": True,  # Required field
            field_name: field_value,
        }

        validator.validate(data)

    def test_schema_composition_with_allof(self, org_workflow_schema):
        """Test that the schema uses allOf for proper composition."""
        # Verify that allOf is used instead of direct $ref
        assert "allOf" in org_workflow_schema
        assert isinstance(org_workflow_schema["allOf"], list)
        assert len(org_workflow_schema["allOf"]) > 0
        assert "$ref" in org_workflow_schema["allOf"][0]
        assert org_workflow_schema["allOf"][0]["$ref"] == "workflow-settings.json"

    def test_repo_schema_composition_with_allof(self, repo_workflow_schema):
        """Test that the repo schema also uses allOf for proper composition."""
        assert "allOf" in repo_workflow_schema
        assert isinstance(repo_workflow_schema["allOf"], list)
        assert len(repo_workflow_schema["allOf"]) > 0
        assert "$ref" in repo_workflow_schema["allOf"][0]
        assert repo_workflow_schema["allOf"][0]["$ref"] == "workflow-settings.json"
