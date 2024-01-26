#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import Optional

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import LivePatch, LivePatchType
from otterdog.models.ruleset import Ruleset
from otterdog.providers.github import GitHubProvider


@dataclasses.dataclass
class RepositoryRuleset(Ruleset):
    """
    Represents a ruleset defined on repo level.
    """

    @property
    def model_object_name(self) -> str:
        return "repo_ruleset"

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> Optional[str]:
        return f"orgs.{jsonnet_config.create_repo_ruleset}"

    @classmethod
    async def apply_live_patch(cls, patch: LivePatch, org_id: str, provider: GitHubProvider) -> None:
        from .repository import Repository

        match patch.patch_type:
            case LivePatchType.ADD:
                assert isinstance(patch.expected_object, RepositoryRuleset)
                assert isinstance(patch.parent_object, Repository)
                await provider.add_repo_ruleset(
                    org_id,
                    patch.parent_object.name,
                    await patch.expected_object.to_provider_data(org_id, provider),
                )

            case LivePatchType.REMOVE:
                assert isinstance(patch.current_object, RepositoryRuleset)
                assert isinstance(patch.parent_object, Repository)
                await provider.delete_repo_ruleset(
                    org_id, patch.parent_object.name, patch.current_object.id, patch.current_object.name
                )

            case LivePatchType.CHANGE:
                assert isinstance(patch.expected_object, RepositoryRuleset)
                assert isinstance(patch.current_object, RepositoryRuleset)
                assert isinstance(patch.parent_object, Repository)
                await provider.update_repo_ruleset(
                    org_id,
                    patch.parent_object.name,
                    patch.current_object.id,
                    await patch.expected_object.to_provider_data(org_id, provider),
                )
