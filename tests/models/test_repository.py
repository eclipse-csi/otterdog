#  *******************************************************************************
#  Copyright (c) 2023 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from otterdog.utils import UNSET
from otterdog.models import Diff
from otterdog.models.repository import Repository

from . import ModelTest


class RepositoryTest(ModelTest):
    @property
    def model_data(self):
        return self.load_json_resource("otterdog-repo.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-repo.json")

    def test_load_from_model(self):
        repo = Repository.from_model(self.model_data)

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

    def test_load_from_provider(self):
        repo = Repository.from_provider(self.provider_data)

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

    def test_patch(self):
        current = Repository.from_model(self.model_data)

        default = Repository.from_model(self.model_data)

        default.name = None
        default.web_commit_signoff_required = True

        patch = current.get_patch_to(default)

        assert len(patch) == 2
        assert patch["name"] == current.name
        assert patch["web_commit_signoff_required"] is current.web_commit_signoff_required

    def test_difference(self):
        current = Repository.from_model(self.model_data)
        other = Repository.from_model(self.model_data)

        other.name = "other"
        other.has_wiki = False

        diff = current.get_difference_to(other)

        assert len(diff) == 2
        assert diff["name"] == Diff(current.name, other.name)
        assert diff["has_wiki"] == Diff(current.has_wiki, other.has_wiki)
