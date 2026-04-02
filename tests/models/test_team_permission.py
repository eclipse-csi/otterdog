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
from otterdog.models.team_permission import TeamPermission
from otterdog.utils import Change

from . import ModelTest


class TeamPermissionTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return TeamPermission.from_model_data(data)

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_org_secret

    @property
    def model_data(self):
        return self.load_json_resource("otterdog-team-permission.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-team-permission.json")

    def test_load_from_model(self):
        team_permission = TeamPermission.from_model_data(self.model_data)

        assert team_permission.name == "TEAM"
        assert team_permission.permission == "pull"

    def test_load_from_provider(self):
        team_permission = TeamPermission.from_provider_data(self.org_id, self.provider_data)

        assert team_permission.name == "TEAM"
        assert team_permission.permission == "pull"

    def test_patch(self):
        current = TeamPermission.from_model_data(self.model_data)
        default = TeamPermission.from_model_data(self.model_data)

        default.permission = "admin"

        patch = current.get_patch_to(default)

        assert len(patch) == 1
        assert patch["permission"] == current.permission

    def test_difference(self):
        current = TeamPermission.from_model_data(self.model_data)
        other = TeamPermission.from_model_data(self.model_data)

        other.permission = "triage"

        diff = current.get_difference_from(other)

        assert len(diff) == 1
        assert diff["permission"] == Change(other.permission, current.permission)
