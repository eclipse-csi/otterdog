#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from io import StringIO
from unittest.mock import AsyncMock, call

import pretend
import pytest

from otterdog.models.repo_workflow_settings import RepositoryWorkflowSettings
from otterdog.models.repository import LivePatch, Repository
from otterdog.operations.plan import PlanOperation
from otterdog.utils import UNSET, Change, IndentingPrinter, jsonnet_evaluate_snippet, query_json
from tests.models import _EXAMPLE_CONFIG


class TestRepository:
    def test_load_from_model(self, repository_test):
        repo = Repository.from_model_data(repository_test.model_data)

        assert repo.name == "otterdog-defaults"
        assert repo.description is None
        assert repo.homepage is None
        assert repo.private is False
        assert repo.has_issues is True
        assert repo.has_projects is True
        assert repo.has_wiki is True
        assert repo.default_branch == "main"
        assert repo.allow_rebase_merge is True
        assert repo.allow_merge_commit is True
        assert repo.allow_squash_merge is True
        assert repo.allow_auto_merge is False
        assert repo.delete_branch_on_merge is False
        assert repo.allow_update_branch is False
        assert repo.squash_merge_commit_title == "COMMIT_OR_PR_TITLE"
        assert repo.squash_merge_commit_message == "COMMIT_MESSAGES"
        assert repo.merge_commit_title == "MERGE_MESSAGE"
        assert repo.merge_commit_message == "PR_TITLE"
        assert repo.archived is False
        assert repo.allow_forking is True
        assert repo.web_commit_signoff_required is False
        assert repo.immutable_releases_enabled is True
        assert repo.secret_scanning == "enabled"
        assert repo.secret_scanning_push_protection is UNSET
        assert repo.dependabot_alerts_enabled is True

        assert repo.aliases == ["oldname"]
        assert repo.post_process_template_content == []
        assert repo.auto_init is False

    def test_load_from_provider(self, repository_test):
        repo = Repository.from_provider_data(repository_test.org_id, repository_test.provider_data)

        assert repo.id == 605555050
        assert repo.node_id == "R_kgDOJBgJag"
        assert repo.name == "otterdog-defaults"
        assert repo.description is None
        assert repo.homepage is None
        assert repo.private is False
        assert repo.has_issues is True
        assert repo.has_projects is True
        assert repo.has_wiki is True
        assert repo.default_branch == "main"
        assert repo.allow_rebase_merge is True
        assert repo.allow_merge_commit is True
        assert repo.allow_squash_merge is True
        assert repo.allow_auto_merge is False
        assert repo.delete_branch_on_merge is False
        assert repo.allow_update_branch is False
        assert repo.squash_merge_commit_title == "COMMIT_OR_PR_TITLE"
        assert repo.squash_merge_commit_message == "COMMIT_MESSAGES"
        assert repo.merge_commit_title == "MERGE_MESSAGE"
        assert repo.merge_commit_message == "PR_TITLE"
        assert repo.archived is False
        assert repo.allow_forking is True
        assert repo.web_commit_signoff_required is False
        assert repo.immutable_releases_enabled is True
        assert repo.secret_scanning == "enabled"
        assert repo.secret_scanning_push_protection == "disabled"
        assert repo.dependabot_alerts_enabled is True

    async def test_to_provider(self, repository_test):
        repo = Repository.from_model_data(repository_test.model_data)

        repo.description = UNSET

        provider_data = await repo.to_provider_data(repository_test.org_id, repository_test.provider)

        assert len(provider_data) == 24
        assert provider_data["name"] == "otterdog-defaults"
        assert provider_data.get("description") is None
        assert provider_data["immutable_releases_enabled"] is True

        assert (query_json("security_and_analysis.secret_scanning.status", provider_data) or "") == "enabled"

    async def test_changes_to_provider(self, repository_test):
        current = Repository.from_model_data(repository_test.model_data)
        other = Repository.from_model_data(repository_test.model_data)

        other.name = "other"
        other.has_wiki = False
        other.secret_scanning = "disabled"

        changes = current.get_difference_from(other)
        provider_data = await Repository.changes_to_provider(repository_test.org_id, changes, repository_test.provider)

        assert len(provider_data) == 3
        assert provider_data["name"] == "otterdog-defaults"
        assert provider_data["has_wiki"] is True
        assert (query_json("security_and_analysis.secret_scanning.status", provider_data) or "") == "enabled"

    def test_patch(self, repository_test):
        current = Repository.from_model_data(repository_test.model_data)

        default = Repository.from_model_data(repository_test.model_data)

        default.name = None
        default.web_commit_signoff_required = True

        patch = current.get_patch_to(default)

        assert len(patch) == 2
        assert patch["name"] == current.name
        assert patch["web_commit_signoff_required"] is current.web_commit_signoff_required

    def test_difference(self, repository_test):
        current = Repository.from_model_data(repository_test.model_data)
        other = Repository.from_model_data(repository_test.model_data)

        other.name = "other"
        other.has_wiki = False

        diff = current.get_difference_from(other)

        assert len(diff) == 2
        assert diff["name"] == Change(other.name, current.name)
        assert diff["has_wiki"] == Change(other.has_wiki, current.has_wiki)

    def test_private_repository_creation_is_cost_related(self, repository_test):
        repo = Repository.from_model_data(repository_test.model_data)
        repo.private = True

        patch = LivePatch.of_addition(repo, None, pretend.stub())

        assert patch.is_cost_related()

    def test_public_repository_creation_is_not_cost_related(self, repository_test):
        repo = Repository.from_model_data(repository_test.model_data)

        patch = LivePatch.of_addition(repo, None, pretend.stub())

        assert not patch.is_cost_related()

    def test_public_to_private_conversion_is_cost_related(self, repository_test):
        expected = Repository.from_model_data(repository_test.model_data)
        current = Repository.from_model_data(repository_test.model_data)
        expected.private = True

        changes = expected.get_difference_from(current)
        patch = LivePatch.of_changes(expected, current, changes, None, False, pretend.stub())

        assert patch.is_cost_related()

    @pytest.mark.parametrize("private", [False, True])
    def test_unrelated_repository_change_is_not_cost_related(self, repository_test, private):
        expected = Repository.from_model_data(repository_test.model_data)
        current = Repository.from_model_data(repository_test.model_data)
        expected.private = current.private = private
        expected.has_issues = False

        changes = expected.get_difference_from(current)
        patch = LivePatch.of_changes(expected, current, changes, None, False, pretend.stub())

        assert not patch.is_cost_related()

    @pytest.mark.parametrize(
        ("expected_workflows", "cost_related"),
        [
            ({"allow_action_patterns": ["actions/checkout@*", "ossf/scorecard-action@*"]}, False),
            ({"max_cache_size_gb": 50}, True),
        ],
    )
    def test_workflow_change_is_cost_related_only_for_cache_size(
        self, repository_test, expected_workflows, cost_related
    ):
        workflows = {
            "enabled": True,
            "allowed_actions": "selected",
            "allow_github_owned_actions": True,
            "allow_verified_creator_actions": False,
            "allow_action_patterns": ["actions/checkout@*"],
            "default_workflow_permissions": "read",
            "actions_can_approve_pull_request_reviews": False,
            "max_cache_size_gb": 10,
        }

        expected = Repository.from_model_data(repository_test.model_data)
        current = Repository.from_model_data(repository_test.model_data)
        current.workflows = RepositoryWorkflowSettings.from_model_data(workflows)
        expected.workflows = RepositoryWorkflowSettings.from_model_data(workflows | expected_workflows)

        changes = expected.get_difference_from(current)
        patch = LivePatch.of_changes(expected, current, changes, None, False, pretend.stub())

        assert "workflows" in changes
        assert patch.is_cost_related() is cost_related

    @pytest.mark.parametrize(
        ("desired_permissions", "deleted_teams"),
        [({"committers": "push"}, ["contributors"]), ({}, ["committers", "contributors"])],
    )
    async def test_team_permission_removals_are_planned_and_applied(
        self, repository_test, desired_permissions, deleted_teams
    ):
        expected = Repository.from_model_data(repository_test.model_data)
        current = Repository.from_model_data(repository_test.model_data)
        expected.set_team_permissions(desired_permissions)
        current.set_team_permissions({"committers": "push", "contributors": "push"})
        changes = expected.get_difference_from(current)

        assert changes["team_permissions"] == Change(current.team_permissions, desired_permissions)

        provider = pretend.stub(
            delete_team_permission=AsyncMock(),
            update_team_permission=AsyncMock(),
            add_team_permission=AsyncMock(),
        )
        patch = LivePatch.of_changes(expected, current, changes, None, False, expected.apply_live_patch)
        await Repository._apply_team_permission_changes(provider, "test-org", expected.name, patch)

        provider.delete_team_permission.assert_has_awaits(
            [call("test-org", expected.name, team) for team in deleted_teams], any_order=True
        )
        assert provider.delete_team_permission.await_count == len(deleted_teams)
        provider.update_team_permission.assert_not_awaited()
        provider.add_team_permission.assert_not_awaited()

    def test_unset_team_permissions_remain_unmanaged(self, repository_test):
        expected = Repository.from_model_data(repository_test.model_data)
        current = Repository.from_model_data(repository_test.model_data)
        current.set_team_permissions({"contributors": "push"})

        assert "team_permissions" not in expected.get_difference_from(current)

    def test_team_permission_removal_is_visible_in_plan(self, repository_test):
        expected = Repository.from_model_data(repository_test.model_data)
        current = Repository.from_model_data(repository_test.model_data)
        expected.set_team_permissions({"committers": "push"})
        current.set_team_permissions({"committers": "push", "contributors": "push"})
        changes = expected.get_difference_from(current)
        output = StringIO()
        operation = PlanOperation(True, "*", False, False, False, "")
        operation.init(pretend.stub(), IndentingPrinter(output, output_for_github=True))

        changed_settings = operation.handle_modified_object("test-org", changes, False, current, expected)

        assert changed_settings == 1
        assert "team_permissions" in output.getvalue()
        assert any(line.strip().startswith("- contributors") for line in output.getvalue().splitlines())

    @pytest.mark.parametrize(
        "gh_pages_source_path, gh_pages_source_branch, expected_changes",
        [
            (
                "/docs",
                None,
                {
                    "gh_pages_source_path": Change("/", "/docs"),
                    "gh_pages_source_branch": Change("gh-pages", "gh-pages"),
                },
            ),
            (
                None,
                "main",
                {
                    "gh_pages_source_branch": Change("gh-pages", "main"),
                    "gh_pages_source_path": Change("/", "/"),
                },
            ),
            (None, None, {}),
            (
                "/docs",
                "main",
                {
                    "gh_pages_source_path": Change("/", "/docs"),
                    "gh_pages_source_branch": Change("gh-pages", "main"),
                },
            ),
        ],
    )
    def test__include_gh_pages_patch_required_properties(
        self,
        repository_test,
        gh_pages_source_path,
        gh_pages_source_branch,
        expected_changes,
    ):
        current = Repository.from_model_data(repository_test.model_data)
        default = Repository.from_model_data(repository_test.model_data)

        # build changes using parametrization if not none
        changes = {}
        if gh_pages_source_path is not None:
            current.gh_pages_source_path = gh_pages_source_path
            changes["gh_pages_source_path"] = Change(default.gh_pages_source_path, gh_pages_source_path)
        if gh_pages_source_branch is not None:
            current.gh_pages_source_branch = gh_pages_source_branch
            changes["gh_pages_source_branch"] = Change(default.gh_pages_source_branch, gh_pages_source_branch)

        test_livepatch = LivePatch(
            patch_type=3,
            expected_object=current,
            current_object=default,
            changes=changes,
            parent_object=None,
            forced_update=False,
            fn=pretend.stub(),
            changes_object_to_readonly=False,
        )
        # Call the function under test
        current._include_gh_pages_patch_required_properties(test_livepatch)

        assert test_livepatch.changes == expected_changes

    @pytest.mark.parametrize(
        "squash_merge_commit_title, squash_merge_commit_message, expected_changes",
        [
            (
                "COMMIT_OR_PR_TITLE",
                "COMMIT_MESSAGES",
                {},
            ),
            (
                "NEW_COMMIT_OR_PR_TITLE",
                "COMMIT_MESSAGES",
                {
                    "squash_merge_commit_title": Change("COMMIT_OR_PR_TITLE", "NEW_COMMIT_OR_PR_TITLE"),
                    "squash_merge_commit_message": Change("COMMIT_MESSAGES", "COMMIT_MESSAGES"),
                },
            ),
            (
                "COMMIT_OR_PR_TITLE",
                "NEW_COMMIT_MESSAGES",
                {
                    "squash_merge_commit_title": Change("COMMIT_OR_PR_TITLE", "COMMIT_OR_PR_TITLE"),
                    "squash_merge_commit_message": Change("COMMIT_MESSAGES", "NEW_COMMIT_MESSAGES"),
                },
            ),
            (
                "NEW_COMMIT_OR_PR_TITLE",
                "NEW_COMMIT_MESSAGES",
                {
                    "squash_merge_commit_title": Change("COMMIT_OR_PR_TITLE", "NEW_COMMIT_OR_PR_TITLE"),
                    "squash_merge_commit_message": Change("COMMIT_MESSAGES", "NEW_COMMIT_MESSAGES"),
                },
            ),
        ],
    )
    def test__include_squash_merge_patch_required_properties(
        self,
        repository_test,
        squash_merge_commit_title,
        squash_merge_commit_message,
        expected_changes,
    ):
        current = Repository.from_model_data(repository_test.model_data)
        default = Repository.from_model_data(repository_test.model_data)

        # build changes using parametrization if not none
        changes = {}
        if squash_merge_commit_title != "COMMIT_OR_PR_TITLE":
            current.squash_merge_commit_title = squash_merge_commit_title
            changes["squash_merge_commit_title"] = Change(default.squash_merge_commit_title, squash_merge_commit_title)
        if squash_merge_commit_message != "COMMIT_MESSAGES":
            current.squash_merge_commit_message = squash_merge_commit_message
            changes["squash_merge_commit_message"] = Change(
                default.squash_merge_commit_message, squash_merge_commit_message
            )

        test_livepatch = LivePatch(
            patch_type=3,
            expected_object=current,
            current_object=default,
            changes=changes,
            parent_object=None,
            forced_update=False,
            fn=pretend.stub(),
            changes_object_to_readonly=False,
        )
        # Call the function under test
        current._include_squash_merge_patch_required_properties(test_livepatch)
        assert test_livepatch.changes == expected_changes

    def test_gh_pages_visibility_validation(self, repository_test):
        """Test that gh_pages_visibility validation works correctly."""
        from otterdog.credentials.inmemory_provider import InMemoryVault
        from otterdog.models import FailureType, ValidationContext

        repo = Repository.from_model_data(repository_test.model_data)
        # Create a minimal context for validation
        context = ValidationContext(
            root_object=None,
            secret_resolver=InMemoryVault(),
            template_dir="",
            org_members=set(),
            default_team_names=set(),
            exclude_teams_pattern=None,
        )

        # Create a mock parent organization object with enterprise plan
        mock_org_enterprise = pretend.stub(
            github_id="test-org",
            settings=pretend.stub(
                plan="enterprise",
                members_can_fork_private_repositories=True,  # Allow forking to avoid conflicts
                members_can_create_private_pages=True,  # Enable private pages
                web_commit_signoff_required=False,
                has_discussions=False,
                has_organization_projects=True,
            ),
        )

        # Create a mock parent organization object with enterprise plan but private pages disabled
        mock_org_enterprise_no_private_pages = pretend.stub(
            github_id="test-org",
            settings=pretend.stub(
                plan="enterprise",
                members_can_fork_private_repositories=True,  # Allow forking to avoid conflicts
                members_can_create_private_pages=False,  # Disable private pages
                web_commit_signoff_required=False,
                has_discussions=False,
                has_organization_projects=True,
            ),
        )

        # Test valid values with enterprise plan and private repo - should not add any failures
        initial_failures = len(context.validation_failures)

        # Set repository to private for valid tests
        repo.private = True

        repo.gh_pages_visibility = "public"
        repo.validate(context, mock_org_enterprise)
        failures = [
            f for f in context.validation_failures if f[0] == FailureType.ERROR and "gh_pages_visibility" in f[1]
        ]
        assert len(failures) == initial_failures

        repo.gh_pages_visibility = "private"
        repo.validate(context, mock_org_enterprise)
        failures = [
            f for f in context.validation_failures if f[0] == FailureType.ERROR and "gh_pages_visibility" in f[1]
        ]
        assert len(failures) == initial_failures

        # Test invalid value - should add a failure
        repo.gh_pages_visibility = "invalid"
        repo.validate(context, mock_org_enterprise)

        # Check that validation failed for invalid value
        failures = [
            f for f in context.validation_failures if f[0] == FailureType.ERROR and "gh_pages_visibility" in f[1]
        ]
        assert len(failures) == 1
        assert "while only values ['public' | 'private'] are allowed" in failures[0][1]

        # Reset for next test
        context.validation_failures.clear()
        repo.gh_pages_visibility = "private"

        # Test with public repository (should fail even with enterprise plan)
        repo.private = False
        repo.validate(context, mock_org_enterprise)

        failures = [
            f for f in context.validation_failures if f[0] == FailureType.ERROR and "gh_pages_visibility" in f[1]
        ]
        assert len(failures) == 1
        assert "only available for private repositories" in failures[0][1]

        # Reset for next test
        context.validation_failures.clear()
        repo.private = True  # Set back to private
        repo.gh_pages_visibility = "private"

        # Test with enterprise plan but members_can_create_private_pages disabled - should fail
        repo.validate(context, mock_org_enterprise_no_private_pages)

        failures = [
            f for f in context.validation_failures if f[0] == FailureType.ERROR and "gh_pages_visibility" in f[1]
        ]
        assert len(failures) == 1
        assert "members_can_create_private_pages' is disabled" in failures[0][1]

    @pytest.mark.parametrize(
        "enforced_repositories,selected_repositories,aliases,expected",
        [
            ("all", [], [], True),
            ("none", ["otterdog-defaults"], [], False),
            ("selected", ["otterdog-defaults"], [], True),
            ("selected", ["Otterdog-Defaults"], [], True),
            ("selected", ["old-name"], ["old-name"], True),
            ("selected", ["other-repo"], [], False),
        ],
    )
    def test_org_enforces_immutable_releases(
        self, repository_test, enforced_repositories, selected_repositories, aliases, expected
    ):
        repo = Repository.from_model_data(repository_test.model_data)
        repo.aliases = aliases

        org_settings = pretend.stub(
            immutable_releases_enforced_repositories=enforced_repositories,
            immutable_releases_selected_repositories=selected_repositories,
        )

        assert repo._org_enforces_immutable_releases(org_settings) is expected

    @staticmethod
    def _generate_immutable_releases_change(
        repository_test, current_enforced, expected_enforced, current_enabled, expected_enabled
    ):
        from otterdog.models import LivePatchContext
        from otterdog.models.organization_settings import OrganizationSettings

        org_settings_data = repository_test.load_json_resource("otterdog-org-settings.json")
        current_org_settings = OrganizationSettings.from_model_data(org_settings_data)
        current_org_settings.immutable_releases_enforced_repositories = current_enforced
        expected_org_settings = OrganizationSettings.from_model_data(org_settings_data)
        expected_org_settings.immutable_releases_enforced_repositories = expected_enforced

        current = Repository.from_model_data(repository_test.model_data)
        current.immutable_releases_enabled = current_enabled
        expected = Repository.from_model_data(repository_test.model_data)
        expected.immutable_releases_enabled = expected_enabled

        context = LivePatchContext("test-org", "", False, False, "*", current_org_settings, expected_org_settings)
        patches = []
        Repository.generate_live_patch(expected, current, None, context, patches.append)

        changes = [
            patch.changes["immutable_releases_enabled"]
            for patch in patches
            if isinstance(patch.expected_object, Repository) and "immutable_releases_enabled" in patch.changes
        ]
        return changes[0] if len(changes) > 0 else None

    @pytest.mark.parametrize("expected_enabled", [True, False])
    def test_live_patch_applies_immutable_releases_when_org_stops_enforcing(self, repository_test, expected_enabled):
        # while enforced by the organization, immutable releases are reported as enabled for the repository,
        # the configured value needs to be applied even if equal, to be kept once the enforcement is removed.
        change = self._generate_immutable_releases_change(repository_test, "all", "none", True, expected_enabled)

        assert change == Change(True, expected_enabled)

    def test_live_patch_ignores_immutable_releases_while_org_enforces(self, repository_test):
        change = self._generate_immutable_releases_change(repository_test, "all", "all", True, False)

        assert change is None

    def test_live_patch_ignores_immutable_releases_when_not_retrieved(self, repository_test):
        change = self._generate_immutable_releases_change(repository_test, "all", "none", UNSET, True)

        assert change is None

    def test_load_gh_pages_custom_domain_from_provider(self, repository_test):
        provider_data = repository_test.provider_data
        provider_data["gh_pages"] = {
            "build_type": "workflow",
            "cname": "docs.example.org",
            "https_enforced": False,
            "public": True,
        }

        repo = Repository.from_provider_data(repository_test.org_id, provider_data)

        assert repo.gh_pages_build_type == "workflow"
        assert repo.gh_pages_cname == "docs.example.org"
        assert repo.gh_pages_https_enforced is False

    async def test_gh_pages_custom_domain_to_provider(self, repository_test):
        repo = Repository.from_model_data(repository_test.model_data)
        repo.gh_pages_cname = "docs.example.org"
        repo.gh_pages_https_enforced = True

        provider_data = await repo.to_provider_data(repository_test.org_id, repository_test.provider)

        assert "gh_pages_cname" not in provider_data
        assert "gh_pages_https_enforced" not in provider_data
        assert provider_data["gh_pages"] == {
            "build_type": "legacy",
            "source": {"branch": "gh-pages", "path": "/"},
            "cname": "docs.example.org",
            "https_enforced": True,
        }

    async def test_gh_pages_https_enforced_ignored_for_default_domain(self, repository_test):
        repo = Repository.from_model_data(repository_test.model_data)
        repo.gh_pages_cname = None
        repo.gh_pages_https_enforced = False

        provider_data = await repo.to_provider_data(repository_test.org_id, repository_test.provider)

        assert provider_data["gh_pages"]["cname"] is None
        assert "https_enforced" not in provider_data["gh_pages"]

        current = Repository.from_model_data(repository_test.model_data)
        current.gh_pages_cname = None
        current.gh_pages_https_enforced = True

        assert repo.get_difference_from(current) == {}

    def test_gh_pages_custom_domain_ignored_when_disabled(self, repository_test):
        expected = Repository.from_model_data(repository_test.model_data)
        expected.gh_pages_build_type = "disabled"
        expected.gh_pages_cname = None

        current = Repository.from_model_data(repository_test.model_data)
        current.gh_pages_build_type = "disabled"
        current.gh_pages_cname = "docs.example.org"

        assert expected.get_difference_from(current) == {}

    @pytest.mark.parametrize(
        "current_cname, expected_cname, expected_changes",
        [
            (
                None,
                "docs.example.org",
                {
                    "gh_pages_cname": Change(None, "docs.example.org"),
                    "gh_pages_https_enforced": Change(True, True),
                },
            ),
            (
                "docs.example.org",
                None,
                {
                    "gh_pages_cname": Change("docs.example.org", None),
                },
            ),
        ],
    )
    def test__include_gh_pages_patch_required_properties_custom_domain(
        self,
        repository_test,
        current_cname,
        expected_cname,
        expected_changes,
    ):
        expected = Repository.from_model_data(repository_test.model_data)
        expected.gh_pages_cname = expected_cname
        expected.gh_pages_https_enforced = True

        current = Repository.from_model_data(repository_test.model_data)
        current.gh_pages_cname = current_cname
        current.gh_pages_https_enforced = True

        test_livepatch = LivePatch(
            patch_type=3,
            expected_object=expected,
            current_object=current,
            changes=expected.get_difference_from(current),
            parent_object=None,
            forced_update=False,
            fn=pretend.stub(),
            changes_object_to_readonly=False,
        )
        expected._include_gh_pages_patch_required_properties(test_livepatch)

        assert test_livepatch.changes == expected_changes

    @pytest.mark.parametrize(
        "cname, error",
        [
            ("docs.example.org", None),
            ("Example.ORG", None),
            ("my-project.eclipse.dev", None),
            ("example", "not a valid domain name"),
            ("https://docs.example.org", "not a valid domain name"),
            ("docs.example.org/path", "not a valid domain name"),
            ("-docs.example.org", "not a valid domain name"),
            ("eclipse-csi.github.io", "can not be a 'github.io' domain"),
        ],
    )
    def test_gh_pages_cname_validation(self, repository_test, cname, error):
        from otterdog.credentials.inmemory_provider import InMemoryVault
        from otterdog.models import FailureType, ValidationContext

        repo = Repository.from_model_data(repository_test.model_data)
        repo.gh_pages_cname = cname

        context = ValidationContext(
            root_object=None,
            secret_resolver=InMemoryVault(),
            template_dir="",
            org_members=set(),
            default_team_names=set(),
            exclude_teams_pattern=None,
        )
        org = pretend.stub(
            github_id="test-org",
            settings=pretend.stub(
                plan="free",
                members_can_fork_private_repositories=True,
                members_can_create_private_pages=False,
                web_commit_signoff_required=False,
                has_discussions=False,
                has_organization_projects=True,
            ),
        )

        repo.validate(context, org)

        failures = [f for f in context.validation_failures if f[0] == FailureType.ERROR and "gh_pages_cname" in f[1]]
        if error is None:
            assert failures == []
        else:
            assert len(failures) == 1
            assert error in failures[0][1]

    @pytest.mark.parametrize(
        "cname, https_enforced, expected_patch",
        [
            (None, True, {}),
            (None, False, {}),
            ("csi.eclipse.dev", True, {"gh_pages_cname": "csi.eclipse.dev"}),
            (
                "csi.eclipse.dev",
                False,
                {"gh_pages_cname": "csi.eclipse.dev", "gh_pages_https_enforced": False},
            ),
        ],
    )
    def test_gh_pages_custom_domain_patch_to_example_config(
        self, repository_test, cname, https_enforced, expected_patch
    ):
        # the patch to the default config is what gets rendered when importing a configuration
        snippet = f"(import '{_EXAMPLE_CONFIG}').{repository_test.template_function}('default')"
        default = Repository.from_model_data(jsonnet_evaluate_snippet(snippet))
        current = Repository.from_model_data(jsonnet_evaluate_snippet(snippet))
        current.gh_pages_build_type = "workflow"
        current.gh_pages_cname = cname
        current.gh_pages_https_enforced = https_enforced

        patch = current.get_patch_to(default)

        assert {k: v for k, v in patch.items() if k in Repository._gh_pages_domain_properties} == expected_patch


@pytest.mark.parametrize(
    "configured,expected",
    [
        (["javascript-typescript"], ["javascript", "typescript"]),
        (["actions", "javascript-typescript", "python"], ["actions", "javascript", "typescript", "python"]),
        (["javascript-typescript", "typescript"], ["javascript", "typescript"]),
        (["javascript", "typescript"], ["javascript", "typescript"]),
        (["python"], ["python"]),
        ([], []),
    ],
)
def test_deprecated_code_scanning_language_is_translated(configured, expected):
    repo = Repository.from_model_data({"name": "my-repo", "code_scanning_default_languages": configured})

    assert repo.code_scanning_default_languages == expected


def test_unset_code_scanning_languages_stay_unset():
    repo = Repository.from_model_data({"name": "my-repo"})

    assert repo.code_scanning_default_languages is UNSET


async def _code_scanning_language_failures(configured, detected):
    repo = Repository.from_model_data(
        {
            "name": "my-repo",
            "code_scanning_default_setup_enabled": True,
            "code_scanning_default_languages": configured,
        }
    )
    failures = []

    async def get_languages(_github_id, _repo_name):
        return dict.fromkeys(detected, 100)

    context = pretend.stub(
        provider=pretend.stub(rest_api=pretend.stub(repo=pretend.stub(get_languages=get_languages))),
        add_failure=lambda failure_type, message: failures.append(message),
    )
    await repo.validate_code_scanning_languages(context, pretend.stub(github_id="my-org"))
    return failures


@pytest.mark.parametrize("detected", [["JavaScript"], ["TypeScript"], ["JavaScript", "TypeScript"]])
async def test_deprecated_code_scanning_language_needs_either_language_detected(detected):
    assert await _code_scanning_language_failures(["javascript-typescript"], detected) == []


async def test_deprecated_code_scanning_language_without_javascript_or_typescript_is_reported():
    failures = await _code_scanning_language_failures(["javascript-typescript"], ["Python"])

    assert len(failures) == 2
    assert any("'javascript'" in failure for failure in failures)
    assert any("'typescript'" in failure for failure in failures)


@pytest.mark.parametrize(
    "configured,detected,missing",
    [
        (["typescript"], ["JavaScript"], "typescript"),
        (["javascript"], ["TypeScript"], "javascript"),
    ],
)
async def test_explicit_single_code_scanning_language_must_be_detected(configured, detected, missing):
    failures = await _code_scanning_language_failures(configured, detected)

    assert len(failures) == 1
    assert f"'{missing}'" in failures[0]
