#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pretend
import pytest

from otterdog.models.repository import LivePatch, Repository
from otterdog.utils import UNSET, Change, query_json


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
        assert repo.secret_scanning == "enabled"
        assert repo.secret_scanning_push_protection == "disabled"
        assert repo.dependabot_alerts_enabled is True

    async def test_to_provider(self, repository_test):
        repo = Repository.from_model_data(repository_test.model_data)

        repo.description = UNSET

        provider_data = await repo.to_provider_data(repository_test.org_id, repository_test.provider)

        assert len(provider_data) == 22
        assert provider_data["name"] == "otterdog-defaults"
        assert provider_data.get("description") is None

        assert query_json("security_and_analysis.secret_scanning.status", provider_data) or "" == "enabled"

    async def test_changes_to_provider(self, repository_test):
        current = Repository.from_model_data(repository_test.model_data)
        other = Repository.from_model_data(repository_test.model_data)

        other.name = "other"
        other.has_wiki = False
        other.secret_scanning = "disabled"

        changes = current.get_difference_from(other)
        provider_data = await Repository.changes_to_provider(self.org_id, changes, self.provider)

        assert len(provider_data) == 3
        assert provider_data["name"] == "otterdog-defaults"
        assert provider_data["has_wiki"] is True
        assert query_json("security_and_analysis.secret_scanning.status", provider_data) or "" == "enabled"

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
                {"gh_pages_source_branch": Change("gh-pages", "main"), "gh_pages_source_path": Change("/", "/")},
            ),
            (None, None, {}),
            (
                "/docs",
                "main",
                {"gh_pages_source_path": Change("/", "/docs"), "gh_pages_source_branch": Change("gh-pages", "main")},
            ),
        ],
    )
    def test__include_gh_pages_patch_required_properties(
        self, repository_test, gh_pages_source_path, gh_pages_source_branch, expected_changes
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
        self, repository_test, squash_merge_commit_title, squash_merge_commit_message, expected_changes
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
