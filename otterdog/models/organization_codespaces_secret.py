#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from otterdog.models import LivePatch, LivePatchType
from otterdog.models.organization_secret import OrganizationSecretBase
from otterdog.utils import unwrap

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


class OrganizationCodespacesSecret(OrganizationSecretBase):
    """Organization-level secret consumed by Codespaces."""

    @property
    def model_object_name(self) -> str:
        return "org_codespaces_secret"

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_org_codespaces_secret}"

    @classmethod
    async def apply_live_patch(
        cls,
        patch: LivePatch[OrganizationCodespacesSecret],
        org_id: str,
        provider: GitHubProvider,
    ) -> None:
        match patch.patch_type:
            case LivePatchType.ADD:
                await provider.add_org_codespaces_secret(
                    org_id,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )
            case LivePatchType.REMOVE:
                await provider.delete_org_codespaces_secret(org_id, unwrap(patch.current_object).name)
            case LivePatchType.CHANGE:
                await provider.update_org_codespaces_secret(
                    org_id,
                    unwrap(patch.current_object).name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )
