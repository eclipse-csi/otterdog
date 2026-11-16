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

from otterdog.logging import get_logger
from otterdog.models import LivePatch, LivePatchType
from otterdog.models.actions_policy import ActionsPolicy
from otterdog.utils import expect_type, unwrap

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider

_logger = get_logger(__name__)


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
                expected_object = unwrap(patch.expected_object)
                # the configuration a merged pull request is applied from may not know a policy of the same name,
                # e.g. created in the web UI or by a previous attempt of a failed apply, which GitHub does not
                # allow to create twice: it is updated instead
                current_data = await provider.get_repo_actions_policy_by_name(
                    org_id, repository.name, expected_object.name
                )
                if current_data is None:
                    await provider.add_repo_actions_policy(
                        org_id,
                        repository.name,
                        await expected_object.to_provider_data(org_id, provider),
                    )
                else:
                    _logger.warning(
                        "actions policy '%s' already exists for repo '%s/%s', updating it",
                        expected_object.name,
                        org_id,
                        repository.name,
                    )
                    current_object = cls.from_provider_data(org_id, current_data)
                    await provider.update_repo_actions_policy(
                        org_id,
                        repository.name,
                        current_object.id,
                        current_object.name,
                        await expected_object.to_provider_data_for_update(current_object, org_id, provider),
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
                await provider.update_repo_actions_policy(
                    org_id,
                    repository.name,
                    current_object.id,
                    current_object.name,
                    await unwrap(patch.expected_object).to_provider_data_for_update(current_object, org_id, provider),
                )
