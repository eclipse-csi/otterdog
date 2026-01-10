#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from otterdog.models import LivePatchType
from otterdog.models.environment import Environment
from otterdog.models.repository import Repository
from otterdog.models.secret import Secret
from otterdog.utils import expect_type, unwrap

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.models import LivePatch
    from otterdog.providers.github import GitHubProvider


@dataclasses.dataclass
class EnvironmentSecret(Secret):
    """
    Represents a Secret defined on environment level.
    """

    @property
    def model_object_name(self) -> str:
        return "environment_secret"

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_environment_secret}"

    @classmethod
    async def apply_live_patch(  # type: ignore[override]
        cls,
        patch: LivePatch[EnvironmentSecret],
        org_id: str,
        provider: GitHubProvider,
    ) -> None:
        environment = expect_type(patch.parent_object, Environment)
        repository = expect_type(environment.parent_repository, Repository)

        match patch.patch_type:
            case LivePatchType.ADD:
                new_object = unwrap(patch.expected_object)
                data = await new_object.to_provider_data(org_id, provider)
                await provider.create_environment_secret(
                    org_id,
                    repository.name,
                    environment.name,
                    data,
                )

            case LivePatchType.REMOVE:
                remove_object = unwrap(patch.current_object)
                await provider.delete_environment_secret(
                    org_id,
                    repository.name,
                    environment.name,
                    remove_object.name,
                )

            case LivePatchType.CHANGE:
                current_obj: EnvironmentSecret = unwrap(patch.current_object)
                expected_obj: EnvironmentSecret = unwrap(patch.expected_object)
                data = await expected_obj.to_provider_data(org_id, provider)
                await provider.update_environment_secret(
                    org_id,
                    repository.name,
                    environment.name,
                    current_obj.name,
                    data,
                )
