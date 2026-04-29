#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from otterdog.models import (
    FailureType,
    LivePatch,
    LivePatchType,
    ModelObject,
    ValidationContext,
)
from otterdog.utils import is_set_and_valid, unwrap

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


_FEATURE_VALUES = {"enabled", "disabled", "not_set"}
_ENFORCEMENT_VALUES = {"enforced", "unenforced"}


@dataclasses.dataclass
class OrganizationCodeSecurityConfiguration(ModelObject):
    """
    Represents a Code Security Configuration defined on organization level.
    """

    id: int = dataclasses.field(metadata={"external_only": True})
    name: str = dataclasses.field(metadata={"key": True})
    description: str
    advanced_security: str
    dependency_graph: str
    dependency_graph_autosubmit_action: str
    dependabot_alerts: str
    dependabot_security_updates: str
    code_scanning_default_setup: str
    secret_scanning: str
    secret_scanning_push_protection: str
    secret_scanning_delegated_bypass: str
    secret_scanning_validity_checks: str
    secret_scanning_non_provider_patterns: str
    private_vulnerability_reporting: str
    enforcement: str

    @property
    def model_object_name(self) -> str:
        return "org_code_security_configuration"

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        feature_fields = (
            "advanced_security",
            "dependency_graph",
            "dependency_graph_autosubmit_action",
            "dependabot_alerts",
            "dependabot_security_updates",
            "code_scanning_default_setup",
            "secret_scanning",
            "secret_scanning_push_protection",
            "secret_scanning_delegated_bypass",
            "secret_scanning_validity_checks",
            "secret_scanning_non_provider_patterns",
            "private_vulnerability_reporting",
        )

        for field_name in feature_fields:
            value = getattr(self, field_name)
            if is_set_and_valid(value) and value not in _FEATURE_VALUES:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has '{field_name}' of value '{value}', "
                    f"while only values ('enabled' | 'disabled' | 'not_set') are allowed.",
                )

        if is_set_and_valid(self.enforcement) and self.enforcement not in _ENFORCEMENT_VALUES:
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header(parent_object)} has 'enforcement' of value '{self.enforcement}', "
                f"while only values ('enforced' | 'unenforced') are allowed.",
            )

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_org_code_security_configuration}"

    @classmethod
    async def apply_live_patch(
        cls,
        patch: LivePatch[OrganizationCodeSecurityConfiguration],
        org_id: str,
        provider: GitHubProvider,
    ) -> None:
        match patch.patch_type:
            case LivePatchType.ADD:
                await provider.add_org_code_security_configuration(
                    org_id,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )

            case LivePatchType.REMOVE:
                current_object = unwrap(patch.current_object)
                await provider.delete_org_code_security_configuration(
                    org_id,
                    current_object.id,
                    current_object.name,
                )

            case LivePatchType.CHANGE:
                current_object = unwrap(patch.current_object)
                await provider.update_org_code_security_configuration(
                    org_id,
                    current_object.id,
                    current_object.name,
                    await unwrap(patch.expected_object).to_provider_data(org_id, provider),
                )
