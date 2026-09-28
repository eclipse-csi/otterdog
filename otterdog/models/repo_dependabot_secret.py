#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from otterdog.models import LivePatch, LivePatchType
from otterdog.models.repo_secret import RepositorySecret
from otterdog.utils import unwrap

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


class RepositoryDependabotSecret(RepositorySecret):
    """Repository-level secret consumed by Dependabot."""

    @property
    def model_object_name(self) -> str:
        return "repo_dependabot_secret"

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_repo_dependabot_secret}"

    @classmethod
    async def apply_live_patch(
        cls,
        patch: LivePatch[Self],
        org_id: str,
        provider: GitHubProvider,
    ) -> None:
        repository_name = cls.repository_name_from_patch(patch)
        match patch.patch_type:
            case LivePatchType.ADD:
                await provider.add_repo_dependabot_secret(
                    org_id,
                    repository_name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )
            case LivePatchType.REMOVE:
                await provider.delete_repo_dependabot_secret(org_id, repository_name, unwrap(patch.current_object).name)
            case LivePatchType.CHANGE:
                await provider.update_repo_dependabot_secret(
                    org_id,
                    repository_name,
                    unwrap(patch.current_object).name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )
