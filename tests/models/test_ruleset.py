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
from pretend import stub

from otterdog.models.organization_ruleset import OrganizationRuleset
from otterdog.models.repo_ruleset import RepositoryRuleset
from otterdog.models.ruleset import PullRequestSettings, Ruleset, StatusCheckSettings
from otterdog.utils import Change


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

    @pytest.mark.parametrize(
        "conditions,remove_conditions",
        [
            # GitHub may return null at any level or omit the conditions key altogether.
            (None, False),
            ({"ref_name": None}, False),
            ({"ref_name": {"include": None, "exclude": None}}, False),
            (None, True),
        ],
        ids=["null_conditions", "null_ref_name", "null_ref_lists", "missing_conditions"],
    )
    def test_disabled_ruleset_with_null_ref_conditions_can_be_diffed(self, conditions, remove_conditions):
        """Disabled ruleset responses can omit ref conditions at any level; treat them as empty when diffing config."""
        data = self.create_ruleset_data([])
        data["enforcement"] = "disabled"
        if remove_conditions:
            data.pop("conditions")
        else:
            data["conditions"] = conditions

        live_ruleset = RepositoryRuleset.from_provider_data(self.org_id, data)
        expected_ruleset = RepositoryRuleset.from_model_data(
            {
                "name": "test-ruleset",
                "target": "branch",
                "enforcement": "disabled",
                "include_refs": ["refs/heads/main"],
            }
        )

        assert live_ruleset.include_refs == []
        assert live_ruleset.exclude_refs == []
        assert expected_ruleset.get_difference_from(live_ruleset)["include_refs"] == Change([], ["refs/heads/main"])

    @pytest.mark.parametrize(
        "conditions,remove_conditions",
        [
            (None, False),
            ({"repository_name": None}, False),
            ({"repository_name": {"include": None, "exclude": None, "protected": None}}, False),
            (None, True),
        ],
        ids=["null_conditions", "null_repository_name", "null_repository_name_filters", "missing_conditions"],
    )
    def test_disabled_org_ruleset_with_null_conditions_can_be_loaded(self, conditions, remove_conditions):
        """Organization rulesets must tolerate missing or null repository-name conditions."""
        data = self.create_ruleset_data([])
        data["enforcement"] = "disabled"
        if remove_conditions:
            data.pop("conditions")
        else:
            data["conditions"] = conditions

        live_ruleset = OrganizationRuleset.from_provider_data(self.org_id, data)

        assert live_ruleset.include_repo_names == []
        assert live_ruleset.exclude_repo_names == []
        assert live_ruleset.protect_repo_names is False

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


class TestStatusCheckSettings:
    def make_provider(self, app_ids: dict[str, int] | None = None):
        async def get_app_ids(app_slugs):
            return {slug: app_ids[slug] for slug in app_slugs}

        return stub(get_app_ids=get_app_ids)

    async def test_get_mapping_to_provider_numeric_integration_id(self):
        # a status check reported only by integration_id (no app_slug) is imported
        # as a bare numeric token, e.g. "15368:Test Summary"; apply must use it
        # directly instead of resolving it as an app slug via GET /apps/{id}.
        data = {"status_checks": ["15368:Test Summary"], "strict": True}
        provider = self.make_provider()

        mapping = await StatusCheckSettings.get_mapping_to_provider("test-org", data, provider)
        result = bend(mapping, data)

        assert result["required_status_checks"] == [{"integration_id": 15368, "context": "Test Summary"}]

    async def test_get_mapping_to_provider_app_slug(self):
        data = {"status_checks": ["github-actions:build"], "strict": True}
        provider = self.make_provider(app_ids={"github-actions": 123})

        mapping = await StatusCheckSettings.get_mapping_to_provider("test-org", data, provider)
        result = bend(mapping, data)

        assert result["required_status_checks"] == [{"integration_id": 123, "context": "build"}]

    async def test_get_mapping_to_provider_any(self):
        data = {"status_checks": ["any:build"], "strict": True}
        provider = self.make_provider()

        mapping = await StatusCheckSettings.get_mapping_to_provider("test-org", data, provider)
        result = bend(mapping, data)

        assert result["required_status_checks"] == [{"context": "build"}]


class TestPullRequestSettings:
    org_id = "test-org"

    def create_ruleset_data_with_pull_request_rule(self, parameters):
        return {
            "id": 123,
            "name": "test-ruleset",
            "enforcement": "active",
            "target": "branch",
            "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
            "bypass_actors": [],
            "rules": [{"type": "pull_request", "parameters": parameters}],
        }

    def make_validation_context(self):
        from otterdog.credentials.inmemory_provider import InMemoryVault
        from otterdog.models import ValidationContext

        return ValidationContext(
            root_object=None,
            secret_resolver=InMemoryVault(),
            template_dir="",
            org_members=set(),
            default_team_names=set(),
            exclude_teams_pattern=None,
        )

    def test_from_provider_reads_allowed_merge_methods(self):
        data = self.create_ruleset_data_with_pull_request_rule(
            {
                "required_approving_review_count": 1,
                "dismiss_stale_reviews_on_push": False,
                "require_code_owner_review": False,
                "require_last_push_approval": False,
                "required_review_thread_resolution": True,
                "allowed_merge_methods": ["merge"],
            }
        )

        ruleset = RepositoryRuleset.from_provider_data(self.org_id, data)

        assert ruleset.required_pull_request is not None
        assert ruleset.required_pull_request.allowed_merge_methods == ["merge"]

    def test_from_provider_defaults_to_all_merge_methods_when_absent(self):
        # Older provider payloads may omit the parameter; GitHub treats an
        # omitted parameter as "all methods allowed".
        data = self.create_ruleset_data_with_pull_request_rule(
            {
                "required_approving_review_count": 1,
                "dismiss_stale_reviews_on_push": False,
                "require_code_owner_review": False,
                "require_last_push_approval": False,
                "required_review_thread_resolution": True,
            }
        )

        ruleset = RepositoryRuleset.from_provider_data(self.org_id, data)

        assert ruleset.required_pull_request is not None
        assert ruleset.required_pull_request.allowed_merge_methods == ["merge", "squash", "rebase"]

    def test_from_model_defaults_to_all_merge_methods_when_omitted(self):
        # A jsonnet template predating the parameter must keep validating and
        # write GitHub's default, so declaring nothing changes nothing.
        settings = PullRequestSettings.from_model_data({"required_approving_review_count": 0})

        assert settings.allowed_merge_methods == ["merge", "squash", "rebase"]

    async def test_get_mapping_to_provider_includes_allowed_merge_methods(self):
        data = {
            "required_approving_review_count": 0,
            "dismisses_stale_reviews": False,
            "requires_code_owner_review": False,
            "requires_last_push_approval": False,
            "requires_review_thread_resolution": True,
            "allowed_merge_methods": ["merge"],
        }

        mapping = await PullRequestSettings.get_mapping_to_provider(self.org_id, data, stub())
        result = bend(mapping, data)

        assert result["allowed_merge_methods"] == ["merge"]
        assert result["required_review_thread_resolution"] is True

    @pytest.mark.parametrize(
        "allowed_merge_methods,expected_failures",
        [
            (["merge"], 0),
            (["merge", "squash", "rebase"], 0),
            ([], 1),
            (["fast-forward"], 1),
            (["merge", "fast-forward", "octopus"], 2),
        ],
        ids=["single_method", "all_methods", "empty_list", "unknown_method", "mixed_valid_invalid"],
    )
    def test_validate_allowed_merge_methods(self, allowed_merge_methods, expected_failures):
        settings = PullRequestSettings.from_model_data(
            {
                "required_approving_review_count": 0,
                "allowed_merge_methods": allowed_merge_methods,
            }
        )
        context = self.make_validation_context()
        parent = stub(get_model_header=lambda parent_object: 'repo_ruleset[name="test-ruleset"]')

        settings.validate(context, parent)

        assert len(context.validation_failures) == expected_failures
