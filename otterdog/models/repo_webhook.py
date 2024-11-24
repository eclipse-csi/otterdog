#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from otterdog.models import LivePatch, LivePatchType
from otterdog.models.webhook import Webhook
from otterdog.utils import expect_type, unwrap

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


@dataclasses.dataclass
class RepositoryWebhook(Webhook):
    """
    Represents a Webhook defined on repo level.
    """

    @property
    def model_object_name(self) -> str:
        return "repo_webhook"

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_repo_webhook}"

    @classmethod
    async def apply_live_patch(
        cls,
        patch: LivePatch[RepositoryWebhook],
        org_id: str,
        provider: GitHubProvider,
    ) -> None:
        from .repository import Repository

        repository = expect_type(patch.parent_object, Repository)

        match patch.patch_type:
            case LivePatchType.ADD:
                await provider.add_repo_webhook(
                    org_id,
                    repository.name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )

            case LivePatchType.REMOVE:
                current_object = unwrap(patch.current_object)
                await provider.delete_repo_webhook(
                    org_id,
                    repository.name,
                    current_object.id,
                    current_object.url,
                )

            case LivePatchType.CHANGE:
                current_object = unwrap(patch.current_object)
                await provider.update_repo_webhook(
                    org_id,
                    repository.name,
                    current_object.id,
                    current_object.url,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )
