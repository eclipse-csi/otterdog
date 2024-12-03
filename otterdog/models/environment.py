#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from jsonbender import F, Filter, Forall, If, K, OptionalS, S  # type: ignore

from otterdog.models import (
    FailureType,
    LivePatch,
    LivePatchType,
    ModelObject,
    ValidationContext,
)
from otterdog.utils import expect_type, is_set_and_valid, is_unset, unwrap

if TYPE_CHECKING:
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider


@dataclasses.dataclass
class Environment(ModelObject):
    """
    Represents a Deployment Environment of a Repository.
    """

    id: int = dataclasses.field(metadata={"external_only": True})
    node_id: str = dataclasses.field(metadata={"external_only": True})
    name: str = dataclasses.field(metadata={"key": True})
    wait_timer: int
    reviewers: list[str]
    deployment_branch_policy: str
    branch_policies: list[str]

    @property
    def model_object_name(self) -> str:
        return "environment"

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        if not is_unset(self.wait_timer) and not (0 <= self.wait_timer <= 43200):
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header(parent_object)} has 'wait_timer' of value '{self.wait_timer}' "
                f"outside of supported range (0, 43200).",
            )

        if is_set_and_valid(self.deployment_branch_policy):
            if self.deployment_branch_policy not in {"all", "protected", "selected"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'deployment_branch_policy' of value "
                    f"'{self.deployment_branch_policy}', "
                    f"while only values ('all' | 'protected' | 'selected') are allowed.",
                )

            if self.deployment_branch_policy != "selected" and len(self.branch_policies) > 0:
                context.add_failure(
                    FailureType.WARNING,
                    f"{self.get_model_header(parent_object)} has 'deployment_branch_policy' set to "
                    f"'{self.deployment_branch_policy}', "
                    f"but 'branch_policies' is set to '{self.branch_policies}', setting will be ignored.",
                )

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        if self.deployment_branch_policy != "selected":
            if field.name in ["branch_policies"]:
                return False

        return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

    def include_existing_object_for_live_patch(self, org_id: str, parent_object: ModelObject | None) -> bool:
        from .repository import Repository

        parent_object = expect_type(parent_object, Repository)

        # if it's a repo in the form of "<orgid>.github.io", ignore a missing github-pages environment
        # as it is automatically created, there is a validation rule to warn the user about it.
        if (parent_object.name.lower() == f"{org_id}.github.io".lower() and self.name == "github-pages") or (
            self.name == "github-pages" and parent_object.gh_pages_build_type != "disabled"
        ):
            return False
        else:
            return True

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        def transform_reviewers(x):
            match x["type"]:
                case "User":
                    return f'@{x["reviewer"]["login"]}'

                case "Team":
                    return f'@{org_id}/{x["reviewer"]["slug"]}'

                case _:
                    raise RuntimeError("unexpected review type '{x[\"type\"]}'")

        def transform_policy(x):
            if x is None:
                return "all"
            else:
                if x.get("protected_branches", False) is True:
                    return "protected"
                elif x.get("custom_branch_policies", False) is True:
                    return "selected"
                else:
                    raise ValueError(f"unexpected deployment_branch_policy {x}")

        def transform_branch_policy(x):
            branch_policy_type = x.get("type", "branch")
            match branch_policy_type:
                case "branch":
                    return x["name"]
                case "tag":
                    return "tag:" + x["name"]
                case _:
                    raise RuntimeError(f"unexpected policy type '{branch_policy_type}'")

        mapping.update(
            {
                "wait_timer": OptionalS("protection_rules", default=[])
                >> Filter(lambda obj: obj.get("type") == "wait_timer")
                >> OptionalS(0, default={})
                >> If(OptionalS("wait_timer") != K(None), S("wait_timer"), K(0)),
                "reviewers": OptionalS("protection_rules", default=[])
                >> Filter(lambda obj: obj.get("type") == "required_reviewers")
                >> OptionalS(0, default={})
                >> OptionalS("reviewers", default=[])
                >> Forall(lambda x: transform_reviewers(x)),
                "deployment_branch_policy": OptionalS("deployment_branch_policy") >> F(transform_policy),
                "branch_policies": OptionalS("branch_policies", default=[]) >> Forall(transform_branch_policy),
            }
        )
        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = await super().get_mapping_to_provider(org_id, data, provider)

        if "reviewers" in mapping:
            reviewers = data["reviewers"]
            reviewer_mapping = []
            for actor_type, (
                actor_id,
                _actor_node_id,
            ) in await provider.get_actor_ids_with_type(reviewers):
                reviewer_mapping.append({"type": actor_type, "id": actor_id})
            mapping["reviewers"] = reviewer_mapping

        if "deployment_branch_policy" in mapping:
            deployment_branch_policy = data["deployment_branch_policy"]

            match deployment_branch_policy:
                case "all":
                    deployment_branch_policy_mapping = None

                case "protected":
                    deployment_branch_policy_mapping = {
                        "protected_branches": True,
                        "custom_branch_policies": False,
                    }

                case "selected":
                    deployment_branch_policy_mapping = {
                        "protected_branches": False,
                        "custom_branch_policies": True,
                    }

                case _:
                    raise RuntimeError(f"unexpected deployment_branch_policy '{deployment_branch_policy}'")

            mapping["deployment_branch_policy"] = deployment_branch_policy_mapping

        return mapping

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_environment}"

    @classmethod
    async def apply_live_patch(cls, patch: LivePatch[Environment], org_id: str, provider: GitHubProvider) -> None:
        from .repository import Repository

        match patch.patch_type:
            case LivePatchType.ADD:
                expected_object = unwrap(patch.expected_object)
                repository = expect_type(patch.parent_object, Repository)
                await provider.add_repo_environment(
                    org_id,
                    repository.name,
                    expected_object.name,
                    await expected_object.to_provider_data(org_id, provider),
                )

            case LivePatchType.REMOVE:
                current_object = unwrap(patch.current_object)
                repository = expect_type(patch.parent_object, Repository)
                await provider.delete_repo_environment(org_id, repository.name, current_object.name)

            case LivePatchType.CHANGE:
                current_object = unwrap(patch.current_object)
                repository = expect_type(patch.parent_object, Repository)
                await provider.update_repo_environment(
                    org_id,
                    repository.name,
                    current_object.name,
                    await cls.changes_to_provider(org_id, unwrap(patch.changes), provider),
                )
