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
    is_set_and_present,
    is_set_and_valid,
    is_unset,
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
    # id of an external group (Enterprise Managed Users) the team is connected to
    external_group_id: int | None
    # identity provider groups connected via team synchronization
    team_sync: list[TeamSync] = dataclasses.field(metadata={"nested_model": True}, default_factory=list)
    skip_members: bool = dataclasses.field(metadata={"model_only": True}, default=False)
    skip_non_organization_members: bool = dataclasses.field(metadata={"model_only": True}, default=False)

    @property
    def model_object_name(self) -> str:
        return "team"

    def add_team_sync(self, ts: TeamSync) -> None:
        self.team_sync.append(ts)

    def is_managed_by_identity_provider(self) -> bool:
        """
        Returns whether the membership of this team is managed by an identity provider,
        either via team synchronization or via an external group.
        """
        return len(self.team_sync) > 0 or is_set_and_present(self.external_group_id)

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_org_team}"

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        if field.name == "members":
            # members of a team connected to an identity provider are provisioned by the IdP
            return not self.skip_members and not self.is_managed_by_identity_provider()

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
                    f"while only values ('secret' | 'visible') are allowed.",
                )

        if self.skip_members is True and is_set_and_valid(self.members) and len(self.members) > 0:
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header(parent_object)} has 'skip_members' enabled, "
                f"but 'members' is set to {self.members}.",
            )

        if (
            is_set_and_valid(self.members)
            and self.skip_non_organization_members is True
            and context.org_members is not None
        ):
            for member in self.members:
                if member not in context.org_members:
                    context.add_failure(
                        FailureType.ERROR,
                        f"{self.get_model_header(parent_object)} has 'skip_non_organization_members' enabled, "
                        f"but 'members' contains user '{member}' who is not an organization member.",
                    )

        self._validate_identity_provider(context, parent_object)

    def _validate_identity_provider(self, context: ValidationContext, parent_object: Any) -> None:
        has_team_sync = len(self.team_sync) > 0
        has_external_group = is_set_and_present(self.external_group_id)

        if has_team_sync and has_external_group:
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header(parent_object)} has 'team_sync' and 'external_group_id' defined, "
                f"while only one of them is allowed.",
            )

        if (
            self.is_managed_by_identity_provider()
            and self.skip_members is False
            and is_set_and_valid(self.members)
            and len(self.members) > 0
        ):
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header(parent_object)} is connected to an identity provider group, "
                f"its members are managed by the identity provider, but 'members' is set to {self.members}.",
            )

        team_sync_ids: set[str] = set()
        for ts in self.team_sync:
            ts.validate(context, self)

            if ts.id in team_sync_ids:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'team_sync' with duplicate group id '{ts.id}'.",
                )
            team_sync_ids.add(ts.id)

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

        def transform_external_groups(groups: Any) -> Any:
            # external groups are only retrieved if supported by the default configuration
            if is_unset(groups):
                return UNSET

            # a team can be connected to a single external group only
            if isinstance(groups, list) and len(groups) > 0:
                return groups[0]["group_id"]

            return None

        mapping.update(
            {
                "privacy": OptionalS("privacy") >> F(lambda x: "visible" if x == "closed" else x),
                "notifications": OptionalS("notification_setting") >> F(transform_notification_setting),
                "members": OptionalS("members", default=[]) >> Forall(transform_team_members),
                "external_group_id": OptionalS("external_groups", default=UNSET) >> F(transform_external_groups),
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
        if len(self.team_sync) == 0:
            super().to_jsonnet(printer, jsonnet_config, context, extend, default_object)
            return

        patch = self.get_patch_to(default_object)
        patch.pop("name", None)

        template_function = self.get_jsonnet_template_function(jsonnet_config, False)
        printer.print(f"{unwrap(template_function)}('{self.name}')")

        write_patch_object_as_json(patch, printer, close_object=False, replace_keys=self.replace_on_patch_keys())

        default_team_sync_config = jsonnet_config.default_team_sync_config
        if default_team_sync_config is None:
            raise RuntimeError(f"no default configuration for '{jsonnet_config.create_org_team_sync}' available")

        default_team_sync = TeamSync.from_model_data(default_team_sync_config)

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
            # the team sync groups are connected once the team is created
            TeamSync.generate_live_patch_of_list(expected_object.team_sync, [], expected_object, context, handler)
            return

        # the team sync groups are updated first, a team connected to an IdP group rejects any change of its members,
        # the current team is used as parent as it knows the slug of the team
        TeamSync.generate_live_patch_of_list(
            expected_object.team_sync, current_object.team_sync, current_object, context, handler
        )

        modified_team: dict[str, Change[Any]] = expected_object.get_difference_from(current_object)

        if cls._remains_managed_by_identity_provider(expected_object, current_object, context):
            modified_team.pop("members", None)

        if len(modified_team) > 0:
            handler(
                LivePatch.of_changes(
                    expected_object,
                    current_object,
                    modified_team,
                    parent_object,
                    False,
                    expected_object.apply_live_patch,
                )
            )

    @staticmethod
    def _remains_managed_by_identity_provider(
        expected_object: Team, current_object: Team, context: LivePatchContext
    ) -> bool:
        """
        Returns whether the team is still connected to an IdP group once the patches are applied,
        in which case its members are provisioned by the IdP and can not be changed.
        """
        if expected_object.is_managed_by_identity_provider():
            return True

        # groups removed from team_sync are only disconnected when deleting resources,
        # while a removed external group is a change of the team that is always applied
        return len(current_object.team_sync) > 0 and not context.delete_resources

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
                current_object = unwrap(patch.current_object)
                await provider.delete_org_team(org_id, current_object.slug, current_object.name)

            case LivePatchType.CHANGE:
                await provider.update_org_team(
                    org_id,
                    unwrap(patch.current_object).slug,
                    unwrap(patch.expected_object).name,
                    await cls.changes_to_provider(org_id, unwrap(patch.changes), provider),
                )
