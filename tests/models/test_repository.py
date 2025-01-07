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
from otterdog.models.repository import Repository
from otterdog.utils import UNSET, Change, query_json

from . import ModelTest


class RepositoryTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return Repository.from_model_data(data)

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_repo

    @property
    def model_data(self):
        return self.load_json_resource("otterdog-repo.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-repo.json")

    def test_load_from_model(self):
        repo = Repository.from_model_data(self.model_data)

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

    def test_load_from_provider(self):
        repo = Repository.from_provider_data(self.org_id, self.provider_data)

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

    async def test_to_provider(self):
        repo = Repository.from_model_data(self.model_data)

        repo.description = UNSET

        provider_data = await repo.to_provider_data(self.org_id, self.provider)

        assert len(provider_data) == 22
        assert provider_data["name"] == "otterdog-defaults"
        assert provider_data.get("description") is None

        assert query_json("security_and_analysis.secret_scanning.status", provider_data) or "" == "enabled"

    async def test_changes_to_provider(self):
        current = Repository.from_model_data(self.model_data)
        other = Repository.from_model_data(self.model_data)

        other.name = "other"
        other.has_wiki = False
        other.secret_scanning = "disabled"

        changes = current.get_difference_from(other)
        provider_data = await Repository.changes_to_provider(self.org_id, changes, self.provider)

        assert len(provider_data) == 3
        assert provider_data["name"] == "otterdog-defaults"
        assert provider_data["has_wiki"] is True
        assert query_json("security_and_analysis.secret_scanning.status", provider_data) or "" == "enabled"

    def test_patch(self):
        current = Repository.from_model_data(self.model_data)

        default = Repository.from_model_data(self.model_data)

        default.name = None
        default.web_commit_signoff_required = True

        patch = current.get_patch_to(default)

        assert len(patch) == 2
        assert patch["name"] == current.name
        assert patch["web_commit_signoff_required"] is current.web_commit_signoff_required

    def test_difference(self):
        current = Repository.from_model_data(self.model_data)
        other = Repository.from_model_data(self.model_data)

        other.name = "other"
        other.has_wiki = False

        diff = current.get_difference_from(other)

        assert len(diff) == 2
        assert diff["name"] == Change(other.name, current.name)
        assert diff["has_wiki"] == Change(other.has_wiki, current.has_wiki)
