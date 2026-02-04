#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import logging
from unittest.mock import patch

import pytest
from jsonbender import bend

from otterdog.models.ruleset import Ruleset


class TestRuleset:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.org_id = "test-org"
        self.roles = {"1": "maintain", "2": "write", "3": "admin"}

    def create_ruleset_data(self, bypass_actors, rules=None):
        return {
            "id": 123,
            "name": "test-ruleset",
            "enforcement": "active",
            "target": "branch",
            "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
            "bypass_actors": bypass_actors,
            "rules": rules or [],
        }

    @pytest.mark.parametrize(
        "test_case,bypass_actors,expected_actors,expected_warnings",
        [
            (
                "missing_team_slug",
                [
                    {
                        "actor_type": "Team",
                        "actor_id": 456,
                        "bypass_mode": "always",
                        # team_slug is missing
                    },
                    {"actor_type": "OrganizationAdmin", "actor_id": 0, "bypass_mode": "always"},
                ],
                ["#OrganizationAdmin"],
                [("fail to map team actor '%s', skipping", 456)],
            ),
            (
                "missing_app_slug",
                [
                    {
                        "actor_type": "Integration",
                        "actor_id": 999,
                        "bypass_mode": "pull_request",
                        # app_slug is missing
                    }
                ],
                [],
                [("fail to map integration actor '%s', skipping", 999)],
            ),
            (
                "all_valid_data",
                [
                    {"actor_type": "Team", "actor_id": 456, "team_slug": "test-org/dev-team", "bypass_mode": "always"},
                    {
                        "actor_type": "Integration",
                        "actor_id": 999,
                        "app_slug": "github-actions",
                        "bypass_mode": "pull_request",
                    },
                    {"actor_type": "OrganizationAdmin", "actor_id": 0, "bypass_mode": "always"},
                    {"actor_type": "RepositoryRole", "actor_id": 1, "bypass_mode": "always"},
                ],
                ["@test-org/dev-team", "github-actions:pull_request", "#OrganizationAdmin", "#maintain"],
                [],
            ),
            (
                "mixed_valid_invalid",
                [
                    {
                        "actor_type": "Team",
                        "actor_id": 111,
                        "team_slug": "test-org/valid-team",
                        "bypass_mode": "always",
                    },
                    {
                        "actor_type": "Team",
                        "actor_id": 222,
                        "bypass_mode": "always",
                        # Missing team_slug
                    },
                    {"actor_type": "Integration", "actor_id": 333, "app_slug": "valid-app", "bypass_mode": "always"},
                    {
                        "actor_type": "Integration",
                        "actor_id": 444,
                        "bypass_mode": "pull_request",
                        # Missing app_slug
                    },
                ],
                ["@test-org/valid-team", "valid-app"],
                [("fail to map team actor '%s', skipping", 222), ("fail to map integration actor '%s', skipping", 444)],
            ),
            (
                "missing_repository_role",
                [
                    {
                        "actor_type": "RepositoryRole",
                        "actor_id": 999,  # Not in roles
                        "bypass_mode": "always",
                    },
                    {
                        "actor_type": "RepositoryRole",
                        "actor_id": 1,  # Valid role ID
                        "bypass_mode": "always",
                    },
                ],
                ["#maintain"],
                [("fail to map repository role '%s', skipping", 999)],
            ),
            (
                "bypass_mode_handling",
                [
                    {
                        "actor_type": "Team",
                        "actor_id": 456,
                        "team_slug": "test-org/dev-team",
                        "bypass_mode": "pull_request",
                    },
                    {
                        "actor_type": "Integration",
                        "actor_id": 999,
                        "app_slug": "github-actions",
                        "bypass_mode": "always",
                    },
                ],
                ["@test-org/dev-team:pull_request", "github-actions"],
                [],
            ),
            ("empty_bypass_actors", [], [], []),
            (
                "unknown_actor_type",
                [
                    {"actor_type": "UnknownType", "actor_id": 999, "bypass_mode": "always"},
                    {"actor_type": "OrganizationAdmin", "actor_id": 0, "bypass_mode": "always"},
                ],
                ["#OrganizationAdmin"],
                [],
            ),
        ],
    )
    def test_get_mapping_from_provider(self, caplog, test_case, bypass_actors, expected_actors, expected_warnings):
        data = self.create_ruleset_data(bypass_actors)

        with (
            caplog.at_level(logging.WARNING, logger="otterdog.models.ruleset"),
            patch.object(Ruleset, "_roles", self.roles),
        ):
            mapping = Ruleset.get_mapping_from_provider(self.org_id, data)

        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warning_records) == len(expected_warnings), (
            f"Test case '{test_case}': Expected {len(expected_warnings)} warnings, got {len(warning_records)}"
        )

        for i, (expected_msg, expected_arg) in enumerate(expected_warnings):
            if i < len(warning_records):
                record = warning_records[i]
                assert expected_msg % expected_arg in record.message, (
                    f"Test case '{test_case}': Warning message mismatch. Expected '{expected_msg % expected_arg}', got '{record.message}'"
                )

        result = bend(mapping, data)
        bypass_actors_result = result["bypass_actors"]

        assert len(bypass_actors_result) == len(expected_actors), (
            f"Test case '{test_case}': Expected {len(expected_actors)} actors, got {len(bypass_actors_result)}"
        )

        for expected_actor in expected_actors:
            assert expected_actor in bypass_actors_result, (
                f"Test case '{test_case}': Expected actor '{expected_actor}' not found in result"
            )

    def test_get_mapping_from_provider_missing_bypass_actors_key(self):
        data = {
            "id": 123,
            "name": "test-ruleset",
            "enforcement": "active",
            "target": "branch",
            "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
            "rules": [],
            # Note: bypass_actors key is missing
        }

        with patch.object(Ruleset, "_roles", self.roles):
            mapping = Ruleset.get_mapping_from_provider(self.org_id, data)

        result = bend(mapping, data)
        bypass_actors_result = result["bypass_actors"]

        assert bypass_actors_result == [], "Missing bypass_actors key should default to empty list"

    def test_get_mapping_from_provider_with_rules(self):
        data = {
            "id": 123,
            "name": "test-ruleset",
            "enforcement": "active",
            "target": "branch",
            "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": ["refs/heads/test"]}},
            "bypass_actors": [],
            "rules": [
                {"type": "deletion"},
                {"type": "creation"},
                {"type": "update"},
                {"type": "non_fast_forward"},
                {"type": "required_signatures"},
                {"type": "required_linear_history"},
                {
                    "type": "pull_request",
                    "parameters": {
                        "dismiss_stale_reviews_on_push": True,
                        "require_code_owner_review": False,
                        "require_last_push_approval": True,
                        "required_approving_review_count": 2,
                        "required_review_thread_resolution": True,
                    },
                },
                {
                    "type": "required_status_checks",
                    "parameters": {
                        "required_status_checks": [{"context": "build", "integration_id": None}],
                        "strict_required_status_checks_policy": True,
                    },
                },
            ],
        }

        with patch.object(Ruleset, "_roles", self.roles):
            mapping = Ruleset.get_mapping_from_provider(self.org_id, data)

        result = bend(mapping, data)

        assert result["allows_deletions"] is False
        assert result["allows_creations"] is False
        assert result["allows_updates"] is False
        assert result["allows_force_pushes"] is False
        assert result["requires_commit_signatures"] is True
        assert result["requires_linear_history"] is True

        assert result["include_refs"] == ["refs/heads/main"]
        assert result["exclude_refs"] == ["refs/heads/test"]

        assert result["required_pull_request"] is not None
        assert result["required_status_checks"] is not None

        assert result["requires_deployments"] is False
        assert result["required_deployment_environments"] == []

        assert result["required_merge_queue"] is None

    def test_get_mapping_from_provider_with_required_deployments(self):
        data = {
            "id": 123,
            "name": "test-ruleset",
            "enforcement": "active",
            "target": "branch",
            "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
            "bypass_actors": [],
            "rules": [
                {
                    "type": "required_deployments",
                    "parameters": {"required_deployment_environments": ["production", "staging"]},
                },
            ],
        }

        with patch.object(Ruleset, "_roles", self.roles):
            mapping = Ruleset.get_mapping_from_provider(self.org_id, data)

        result = bend(mapping, data)

        assert result["requires_deployments"] is True
        assert result["required_deployment_environments"] == ["production", "staging"]

    def test_get_mapping_from_provider_with_merge_queue(self):
        """Test that merge_queue rule is processed correctly."""
        data = {
            "id": 123,
            "name": "test-ruleset",
            "enforcement": "active",
            "target": "branch",
            "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
            "bypass_actors": [],
            "rules": [
                {
                    "type": "merge_queue",
                    "parameters": {
                        "check_response_timeout_minutes": 60,
                        "grouping_strategy": "ALLGREEN",
                        "max_entries_to_build": 5,
                        "max_entries_to_merge": 3,
                        "merge_method": "SQUASH",
                        "min_entries_to_merge": 1,
                        "min_entries_to_merge_wait_minutes": 0,
                    },
                },
            ],
        }

        with patch.object(Ruleset, "_roles", self.roles):
            mapping = Ruleset.get_mapping_from_provider(self.org_id, data)

        result = bend(mapping, data)

        assert result["required_merge_queue"] is not None
