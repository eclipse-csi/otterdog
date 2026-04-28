#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import abc
import dataclasses
from typing import TYPE_CHECKING, Any, TypeVar

from jsonbender import F, Forall, OptionalS, S  # type: ignore

from otterdog.models import (
    FailureType,
    LivePatch,
    LivePatchContext,
    LivePatchHandler,
    LivePatchType,
    ModelObject,
    PatchContext,
    ValidationContext,
)
from otterdog.models.team_sync import TeamSync
from otterdog.utils import (
    UNSET,
    Change,
    IndentingPrinter,
    is_set_and_valid,
    unwrap,
    write_patch_object_as_json,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider

TT = TypeVar("TT", bound="Team")


@dataclasses.dataclass
class Team(ModelObject, abc.ABC):
    """
    Represents a Team.
    """

    id: int = dataclasses.field(metadata={"external_only": True})
    slug: str = dataclasses.field(metadata={"external_only": True})
    name: str = dataclasses.field(metadata={"key": True})
    description: str | None
    privacy: str
    notifications: bool
    members: list[str]
    external_groups: str | None
    team_sync: list[TeamSync] = dataclasses.field(metadata={"nested_model": True}, default_factory=list)
    skip_members: bool = dataclasses.field(metadata={"model_only": True}, default=False)
    skip_non_organization_members: bool = dataclasses.field(metadata={"model_only": True}, default=False)

    @property
    def model_object_name(self) -> str:
        return "team"

    def add_team_sync(self, ts: TeamSync) -> None:
        self.team_sync.append(ts)

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_org_team}"

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        if field.name == "members":
            return not self.skip_members

        return True

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        # execute custom validation rules if present
        self.execute_custom_validation_if_present(context, "validate-team.py")

        if (
            context.exclude_teams_pattern is not None
            and context.exclude_teams_pattern.match(self.name)
            and self.name not in context.default_team_names
        ):
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header(parent_object)} has 'name' of value '{self.name}', "
                f"which is not allowed due to exclusion pattern '{context.exclude_teams_pattern.pattern}'.",
            )

        if is_set_and_valid(self.privacy):
            if self.privacy not in {"secret", "visible"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'privacy' of value '{self.privacy}', "
                    f"while only values ('secret' | 'closed') are allowed.",
                )

        if self.skip_members is True and is_set_and_valid(self.members) and len(self.members) > 0:
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header(parent_object)} has 'skip_members' enabled, "
                f"but 'members' is set to {self.members}.",
            )

        if is_set_and_valid(self.members) and self.skip_non_organization_members is True:
            for member in self.members:
                if member not in context.org_members:
                    context.add_failure(
                        FailureType.ERROR,
                        f"{self.get_model_header(parent_object)} has 'skip_non_organization_members' enabled, "
                        f"but 'members' contains user '{member}' who is not an organization member.",
                    )

        for ts in self.team_sync:
            ts.validate(context, self)

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        def transform_notification_setting(x: str | None):
            if x is None:
                return UNSET
            elif x == "notifications_enabled":
                return True
            else:
                return False

        def transform_team_members(member):
            return member["login"]

        def transform_external_groups(value):
            if isinstance(value, list) and value:
                return value[0]["group_id"]
            return None

        mapping.update(
            {
                "privacy": OptionalS("privacy") >> F(lambda x: "visible" if x == "closed" else x),
                "notifications": OptionalS("notification_setting") >> F(transform_notification_setting),
                "members": OptionalS("members", default=[]) >> Forall(transform_team_members),
                "external_groups": OptionalS("external_groups") >> F(transform_external_groups),
            }
        )
        return mapping

    def get_model_objects(self) -> Iterator[tuple[ModelObject, ModelObject]]:
        for ts in self.team_sync:
            yield ts, self
            yield from ts.get_model_objects()

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = await super().get_mapping_to_provider(org_id, data, provider)

        if "privacy" in data:
            mapping["privacy"] = S("privacy") >> F(lambda x: "closed" if x == "visible" else x)

        if "notifications" in data:
            mapping["notification_setting"] = S("notifications") >> F(
                lambda x: "notifications_enabled" if x is True else "notifications_disabled"
            )
            mapping.pop("notifications")

        return mapping

    @classmethod
    def get_mapping_from_model(cls) -> dict[str, Any]:
        mapping = super().get_mapping_from_model()

        mapping.update(
            {
                "team_sync": OptionalS("team_sync", default=[]) >> Forall(lambda x: TeamSync.from_model_data(x)),
            }
        )
        return mapping

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        jsonnet_config: JsonnetConfig,
        context: PatchContext,
        extend: bool,
        default_object: ModelObject,
    ) -> None:

        has_team_sync = len(self.team_sync) > 0

        patch = self.get_patch_to(default_object)

        template_function = self.get_jsonnet_template_function(jsonnet_config, False)

        printer.print(f"{unwrap(template_function)}('{self.name}')")

        write_patch_object_as_json(patch, printer, False)

        if has_team_sync and not extend:
            default_team_sync = TeamSync.from_model_data(jsonnet_config.default_team_sync_config)
            printer.println("team_sync: [")
            printer.level_up()

            for ts in self.team_sync:
                ts.to_jsonnet(printer, jsonnet_config, context, False, default_team_sync)

            printer.level_down()
            printer.println("],")

        # close the team object
        printer.level_down()
        printer.println("},")

    @classmethod
    def generate_live_patch(
        cls,
        expected_object: Team | None,
        current_object: Team | None,
        parent_object: ModelObject | None,
        context: LivePatchContext,
        handler: LivePatchHandler,
    ) -> None:
        if expected_object is None:
            current_object = unwrap(current_object)
            handler(LivePatch.of_deletion(current_object, parent_object, current_object.apply_live_patch))
            return

        if current_object is None:
            handler(LivePatch.of_addition(expected_object, parent_object, expected_object.apply_live_patch))
        else:
            modified_rule: dict[str, Change[Any]] = expected_object.get_difference_from(current_object)

            if len(modified_rule) > 0:
                handler(
                    LivePatch.of_changes(
                        expected_object,
                        current_object,
                        modified_rule,
                        parent_object,
                        False,
                        expected_object.apply_live_patch,
                    )
                )

        TeamSync.generate_live_patch_of_list(
            expected_object.team_sync,
            current_object.team_sync if current_object is not None else [],
            expected_object,
            context,
            handler,
        )

    @classmethod
    async def apply_live_patch(
        cls,
        patch: LivePatch[Team],
        org_id: str,
        provider: GitHubProvider,
    ) -> None:
        match patch.patch_type:
            case LivePatchType.ADD:
                expected_object = unwrap(patch.expected_object)
                await provider.add_org_team(
                    org_id,
                    expected_object.name,
                    await expected_object.to_provider_data(org_id, provider),
                )

            case LivePatchType.REMOVE:
                await provider.delete_org_team(org_id, unwrap(patch.current_object).slug)

            case LivePatchType.CHANGE:
                await provider.update_org_team(
                    org_id,
                    unwrap(patch.current_object).slug,
                    unwrap(patch.expected_object).name,
                    await cls.changes_to_provider(org_id, unwrap(patch.changes), provider),
                )
