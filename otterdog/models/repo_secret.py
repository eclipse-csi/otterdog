#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Self

from otterdog.models import LivePatch, LivePatchType
from otterdog.models.secret import Secret
from otterdog.utils import unwrap

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


@dataclasses.dataclass
class RepositorySecret(Secret):
    """
    Represents a Secret defined on repo level.
    """

    @property
    def model_object_name(self) -> str:
        return "repo_secret"

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_repo_secret}"

    @classmethod
    def repository_name_from_patch(cls, patch: LivePatch[Self]) -> str:
        """Return the repository name after validating a repository-secret patch parent.

        Repository secrets cannot import ``Repository`` at module scope because the
        repository model imports the secret model.  The model-object discriminator
        gives us the same runtime validation without recreating that circular import.
        """
        parent_object = patch.parent_object
        if parent_object is None or parent_object.model_object_name != "repository":
            raise TypeError("repository secret patches require a repository parent")

        repository_name = getattr(parent_object, "name", None)
        if not isinstance(repository_name, str):
            raise TypeError("repository secret patch parent must have a repository name")
        return repository_name

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
                await provider.add_repo_secret(
                    org_id,
                    repository_name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )

            case LivePatchType.REMOVE:
                await provider.delete_repo_secret(
                    org_id,
                    repository_name,
                    unwrap(patch.current_object).name,
                )

            case LivePatchType.CHANGE:
                await provider.update_repo_secret(
                    org_id,
                    repository_name,
                    unwrap(patch.current_object).name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )
