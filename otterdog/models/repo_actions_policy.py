#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from otterdog.models import LivePatch, LivePatchType
from otterdog.models.actions_policy import ActionsPolicy
from otterdog.utils import expect_type, unwrap

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


@dataclasses.dataclass
class RepositoryActionsPolicy(ActionsPolicy):
    """
    Represents an Actions policy defined on repository level.
    """

    @property
    def model_object_name(self) -> str:
        return "repo_actions_policy"

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_repo_actions_policy}"

    @classmethod
    async def apply_live_patch(
        cls,
        patch: LivePatch[RepositoryActionsPolicy],
        org_id: str,
        provider: GitHubProvider,
    ) -> None:
        from .repository import Repository

        repository = expect_type(patch.parent_object, Repository)

        match patch.patch_type:
            case LivePatchType.ADD:
                await provider.add_repo_actions_policy(
                    org_id,
                    repository.name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )

            case LivePatchType.REMOVE:
                current_object = unwrap(patch.current_object)
                await provider.delete_repo_actions_policy(
                    org_id,
                    repository.name,
                    current_object.id,
                    current_object.name,
                )

            case LivePatchType.CHANGE:
                current_object = unwrap(patch.current_object)
                expected_object = unwrap(patch.expected_object).with_unset_values_from(current_object)
                await provider.update_repo_actions_policy(
                    org_id,
                    repository.name,
                    current_object.id,
                    current_object.name,
                    current_object.with_unsupported_settings(await expected_object.to_provider_data(org_id, provider)),
                )
