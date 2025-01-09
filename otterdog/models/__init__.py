#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, Protocol, Self, TypeVar, cast, final

from jsonbender import OptionalS, S, bend  # type: ignore

from otterdog.utils import (
    UNSET,
    Change,
    IndentingPrinter,
    T,
    associate_by_key,
    is_different_ignoring_order,
    is_set_and_valid,
    is_unset,
    multi_associate_by_key,
    patch_to_other,
    unwrap,
    write_patch_object_as_json,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, Sequence
    from re import Pattern

    from otterdog.config import SecretResolver
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider

MT = TypeVar("MT", bound="ModelObject")
EMT = TypeVar("EMT", bound="EmbeddedModelObject")


class FailureType(Enum):
    INFO = 1
    WARNING = 2
    ERROR = 3


@dataclasses.dataclass
class ValidationContext:
    root_object: Any
    secret_resolver: SecretResolver
    template_dir: str
    org_members: set[str]
    default_team_names: set[str]
    exclude_teams_pattern: Pattern | None
    validation_failures: list[tuple[FailureType, str]] = dataclasses.field(default_factory=list)

    def add_failure(self, failure_type: FailureType, message: str):
        self.validation_failures.append((failure_type, message))

    def property_equals(self, model_object, key, value):
        current_value = model_object.__getattribute__(key)
        if current_value != value:
            self.add_failure(
                FailureType.ERROR,
                f"{model_object.get_model_header()} has '{key}' set to '{current_value}' but '{value}' is required.",
            )


class LivePatchType(Enum):
    ADD = 1
    REMOVE = 2
    CHANGE = 3


class LivePatchApplyFn(Protocol[MT]):
    async def __call__(self, patch: LivePatch[MT], org_id: str, provider: GitHubProvider) -> None: ...


@dataclasses.dataclass(frozen=True)
class LivePatch(Generic[MT]):
    patch_type: LivePatchType
    expected_object: MT | None
    current_object: MT | None
    changes: dict[str, Change] | None
    parent_object: ModelObject | None
    forced_update: bool
    fn: LivePatchApplyFn
    changes_object_to_readonly: bool = False

    @classmethod
    def of_addition(cls, expected_object: MT, parent_object: ModelObject | None, fn: LivePatchApplyFn[MT]) -> LivePatch:
        return LivePatch(LivePatchType.ADD, expected_object, None, None, parent_object, False, fn)

    @classmethod
    def of_deletion(cls, current_object: MT, parent_object: ModelObject | None, fn: LivePatchApplyFn[MT]) -> LivePatch:
        return LivePatch(LivePatchType.REMOVE, None, current_object, None, parent_object, False, fn)

    @classmethod
    def of_changes(
        cls,
        expected_object: MT,
        current_object: MT,
        changes: dict[str, Change],
        parent_object: ModelObject | None,
        forced_update: bool,
        fn: LivePatchApplyFn[MT],
        changes_object_to_readonly: bool = False,
    ) -> LivePatch:
        return LivePatch(
            LivePatchType.CHANGE,
            expected_object,
            current_object,
            changes,
            parent_object,
            forced_update,
            fn,
            changes_object_to_readonly,
        )

    def requires_web_ui(self) -> bool:
        match self.patch_type:
            case LivePatchType.ADD:
                return unwrap(self.expected_object).requires_web_ui()

            case LivePatchType.REMOVE:
                return False

            case LivePatchType.CHANGE:
                return unwrap(self.expected_object).changes_require_web_ui(unwrap(self.changes))

    def requires_secrets(self) -> bool:
        match self.patch_type:
            case LivePatchType.ADD:
                return unwrap(self.expected_object).contains_secrets()

            case LivePatchType.REMOVE:
                return False

            case LivePatchType.CHANGE:
                return unwrap(self.expected_object).contains_secrets()

    async def apply(self, org_id: str, provider: GitHubProvider) -> None:
        await self.fn(self, org_id, provider)

    def __repr__(self) -> str:
        obj = self.expected_object if self.expected_object is not None else self.current_object
        return f"{self.patch_type.name} - {unwrap(obj).get_model_header(self.parent_object)}"


@dataclasses.dataclass
class PatchContext:
    org_id: str
    org_settings: ModelObject


@dataclasses.dataclass
class LivePatchContext:
    org_id: str
    repo_filter: str
    update_webhooks: bool
    update_secrets: bool
    update_filter: str
    current_org_settings: ModelObject | None
    expected_org_settings: ModelObject
    modified_org_settings: dict[str, Change] = dataclasses.field(default_factory=dict)
    modified_org_workflow_settings: dict[str, Change] = dataclasses.field(default_factory=dict)


class LivePatchHandler(Protocol):
    def __call__(self, patch: LivePatch) -> None: ...


@dataclasses.dataclass
class EmbeddedModelObject(ABC):
    """
    The abstract base class for embedded model objects.
    """

    @abstractmethod
    def validate(self, context: ValidationContext, parent_object: Any) -> None: ...

    def get_difference_from(self, other: Self) -> Change | None:
        if not isinstance(other, self.__class__):
            raise ValueError(f"'types do not match: {type(self)}' != '{type(other)}'")

        from_dict: dict[str, Any] = {}
        to_dict: dict[str, Any] = {}

        for key in self.keys(
            for_diff=True,
            for_patch=False,
            exclude_unset_keys=True,
        ):
            to_value = self.__getattribute__(key)
            from_value = other.__getattribute__(key)

            if is_unset(from_value):
                continue

            from_dict[key] = from_value
            to_dict[key] = to_value

        if is_different_ignoring_order(from_dict, to_dict):
            return Change(from_dict, to_dict)
        else:
            return None

    def get_patch_to(self, other: EmbeddedModelObject) -> dict[str, Any]:
        if not isinstance(other, self.__class__):
            raise ValueError(f"'types do not match: {type(self)}' != '{type(other)}'")

        patch_result = {}
        for key in self.keys(for_diff=False, for_patch=True, exclude_unset_keys=True):
            value = self.__getattribute__(key)
            other_value = other.__getattribute__(key)

            if is_unset(other_value):
                continue

            patch_needed, diff = patch_to_other(value, other_value)
            if patch_needed is True:
                patch_result[key] = diff

        return patch_result

    @abstractmethod
    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None: ...

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        jsonnet_config: JsonnetConfig,
        context: PatchContext,
        extend: bool,
        default_object: EmbeddedModelObject,
    ) -> None:
        patch = self.get_patch_to(default_object)

        template_function = self.get_jsonnet_template_function(jsonnet_config, False)

        if extend is False:
            printer.print(f" {unwrap(template_function)}()")

        write_patch_object_as_json(patch, printer)

    @classmethod
    def all_fields(cls) -> list[dataclasses.Field]:
        return list(dataclasses.fields(cls))

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return self.include_field_for_diff_computation(field)

    def keys(
        self,
        for_diff: bool = False,
        for_patch: bool = False,
        exclude_unset_keys: bool = True,
    ) -> list[str]:
        result = []

        for field in self.all_fields():
            if for_diff is True and not self.include_field_for_diff_computation(field):
                continue

            if for_patch is True and not self.include_field_for_patch_computation(field):
                continue

            if exclude_unset_keys:
                value = self.__getattribute__(field.name)
                if not is_unset(value):
                    result.append(field.name)
            else:
                result.append(field.name)

        return result

    def to_model_dict(self, for_diff: bool = False) -> dict[str, Any]:
        result = {}

        for key in self.keys(for_diff=for_diff, for_patch=False, exclude_unset_keys=True):
            value = self.__getattribute__(key)
            result[key] = value

        return result

    @classmethod
    def from_model_data(cls: type[EMT], data: dict[str, Any]) -> EMT:
        mapping = cls.get_mapping_from_model()
        return cls(**bend(mapping, data))  # type: ignore

    @classmethod
    def get_mapping_from_model(cls) -> dict[str, Any]:
        return {k: OptionalS(k, default=UNSET) for k in (x.name for x in cls.all_fields())}

    @classmethod
    def from_provider_data(cls: type[EMT], org_id: str, data: dict[str, Any]) -> EMT:
        mapping = cls.get_mapping_from_provider(org_id, data)
        return cls(**bend(mapping, data))  # type: ignore

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return {k: OptionalS(k, default=UNSET) for k in (x.name for x in cls.all_fields())}

    @classmethod
    async def dict_to_provider_data(cls, org_id: str, data: dict[str, Any], provider: GitHubProvider) -> dict[str, Any]:
        mapping = await cls.get_mapping_to_provider(org_id, data, provider)
        return bend(mapping, data)

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        return {field.name: S(field.name) for field in cls.all_fields() if not is_unset(data.get(field.name, UNSET))}


@dataclasses.dataclass
class ModelObject(ABC):
    """
    The abstract base class for any model object.
    """

    def __post_init__(self):
        """
        Assigns to all field which are UNSET their default value, if one is available.
        """
        for field in self.all_fields():
            value = self.__getattribute__(field.name)
            if is_unset(value):
                if field.default is not dataclasses.MISSING:
                    self.__setattr__(field.name, field.default)
                elif field.default_factory is not dataclasses.MISSING:
                    self.__setattr__(field.name, field.default_factory())

    @property
    @abstractmethod
    def model_object_name(self) -> str: ...

    def is_keyed(self) -> bool:
        """Indicates whether the ModelObject is keyed by a property"""
        return any(field.metadata.get("key", False) for field in self.all_fields())

    def get_key(self) -> str:
        """Returns the key property of this ModelObject if it keyed"""
        if not self.is_keyed():
            raise RuntimeError("model object is not keyed")

        return next(
            filter(
                lambda field: field.metadata.get("key", False) is True,
                self.all_fields(),
            )
        ).name

    def get_key_value(self) -> Any:
        """Returns the value of the key property"""
        return self.__getattribute__(self.get_key())

    def get_all_key_values(self) -> list[Any]:
        """Returns a list of all values by which this ModelObject is keyed"""
        return [self.get_key_value()]

    @abstractmethod
    def validate(self, context: ValidationContext, parent_object: Any) -> None: ...

    # noinspection PyMethodMayBeStatic
    def execute_custom_validation_if_present(self, context: ValidationContext, filename: str) -> None:
        validate_script = os.path.join(context.template_dir, filename)
        if os.path.exists(validate_script):
            with open(validate_script) as file:
                exec(file.read())

    def get_difference_from(self, other: Self) -> dict[str, Change[T]]:
        if not isinstance(other, self.__class__):
            raise ValueError(f"'types do not match: {type(self)}' != '{type(other)}'")

        diff_result: dict[str, Change[T]] = {}
        for key in self.keys(
            for_diff=True,
            for_patch=False,
            include_nested_models=False,
            exclude_unset_keys=True,
        ):
            to_value = self.__getattribute__(key)
            from_value = other.__getattribute__(key)

            if not other.is_key_valid_for_diff_computation(key, self):
                continue

            if is_unset(from_value):
                continue

            if isinstance(to_value, EmbeddedModelObject) and isinstance(from_value, EmbeddedModelObject):
                embedded_diff = to_value.get_difference_from(from_value)
                if embedded_diff is not None:
                    diff_result[key] = embedded_diff
                continue

            if isinstance(to_value, EmbeddedModelObject):
                to_value = to_value.to_model_dict()

            if isinstance(from_value, EmbeddedModelObject):
                from_value = from_value.to_model_dict()

            # TODO: improve diff computation for embedded model objects
            #       right now a simple dict comparison is being made
            #       but that does not take UNSET values into account
            if is_different_ignoring_order(to_value, from_value):
                diff_result[key] = Change(from_value, to_value)

        return diff_result

    def get_patch_to(self, other: ModelObject) -> dict[str, Any]:
        if not isinstance(other, self.__class__):
            raise ValueError(f"'types do not match: {type(self)}' != '{type(other)}'")

        patch_result = {}
        for key in self.keys(
            for_diff=False,
            for_patch=True,
            include_nested_models=False,
            exclude_unset_keys=True,
        ):
            value = self.__getattribute__(key)
            other_value = other.__getattribute__(key)

            if is_unset(other_value):
                continue

            patch_needed, diff = patch_to_other(value, other_value)
            if patch_needed is True:
                patch_result[key] = diff

        return patch_result

    @classmethod
    def all_fields(cls) -> list[dataclasses.Field]:
        return list(dataclasses.fields(cls))

    @classmethod
    def model_fields(cls) -> list[dataclasses.Field]:
        return [field for field in dataclasses.fields(cls) if not cls.is_external_only(field)]

    @classmethod
    def model_only_fields(cls) -> list[dataclasses.Field]:
        return [field for field in dataclasses.fields(cls) if cls.is_model_only(field)]

    @classmethod
    def provider_fields(cls) -> list[dataclasses.Field]:
        return [
            field
            for field in dataclasses.fields(cls)
            if not cls.is_external_only(field)
            and not cls.is_model_only(field)
            and not cls.is_read_only(field)
            and not cls.is_nested_model(field)
        ]

    @classmethod
    def _get_field(cls, key: str) -> dataclasses.Field:
        for field in dataclasses.fields(cls):
            if field.name == key:
                return field

        raise ValueError(f"unknown key {key}")

    @staticmethod
    def is_external_only(field: dataclasses.Field) -> bool:
        return field.metadata.get("external_only", False) is True

    @staticmethod
    def is_read_only(field: dataclasses.Field) -> bool:
        return field.metadata.get("read_only", False) is True

    @classmethod
    def is_read_only_key(cls, key: str) -> bool:
        return cls.is_read_only(cls._get_field(key))

    @classmethod
    def is_nested_model_key(cls, key: str) -> bool:
        return cls.is_nested_model(cls._get_field(key))

    @classmethod
    def is_embedded_model_key(cls, key: str) -> bool:
        return cls.is_embedded_model(cls._get_field(key))

    @staticmethod
    def is_model_only(field: dataclasses.Field) -> bool:
        return field.metadata.get("model_only", False) is True

    @staticmethod
    def is_nested_model(field: dataclasses.Field) -> bool:
        return field.metadata.get("nested_model", False) is True

    @staticmethod
    def is_embedded_model(field: dataclasses.Field) -> bool:
        return field.metadata.get("embedded_model", False) is True

    def get_model_objects(self) -> Iterator[tuple[ModelObject, ModelObject]]:
        yield from []

    def get_model_header(self, parent_object: ModelObject | None = None) -> str:
        header = f"[bold]{self.model_object_name}[/]"

        if self.is_keyed():
            key = self.get_key()
            header = header + f'\\[{key}="[bold]{self.get_key_value()}[/]"'

            if isinstance(parent_object, ModelObject) and parent_object.is_keyed():
                header = header + f", {parent_object.model_object_name}=" + f"[bold]{parent_object.get_key_value()}[/]"

            header = header + "]"
        elif isinstance(parent_object, ModelObject) and parent_object.is_keyed():
            header = header + "\\["
            header = header + f"{parent_object.model_object_name}=" + f"[bold]{parent_object.get_key_value()}[/]"
            header = header + "]"

        return header

    @classmethod
    @final
    def from_model_data(cls: type[MT], data: Mapping[str, Any]) -> MT:
        mapping = cls.get_mapping_from_model()
        return cls(**bend(mapping, data))  # type: ignore

    @classmethod
    def get_mapping_from_model(cls) -> dict[str, Any]:
        return {k: OptionalS(k, default=UNSET) for k in (x.name for x in cls.all_fields())}

    @classmethod
    @final
    def from_provider_data(cls: type[MT], org_id: str, data: dict[str, Any]) -> MT:
        mapping = cls.get_mapping_from_provider(org_id, data)
        return cls(**bend(mapping, data))  # type: ignore

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return {k: OptionalS(k, default=UNSET) for k in (x.name for x in cls.all_fields())}

    async def to_provider_data(self, org_id: str, provider: GitHubProvider) -> dict[str, Any]:
        return await self.dict_to_provider_data(org_id, self.to_model_dict(), provider)

    @classmethod
    async def changes_to_provider(
        cls, org_id: str, data: dict[str, Change[Any]], provider: GitHubProvider
    ) -> dict[str, Any]:
        return await cls.dict_to_provider_data(org_id, {key: change.to_value for key, change in data.items()}, provider)

    @classmethod
    async def dict_to_provider_data(cls, org_id: str, data: dict[str, Any], provider: GitHubProvider) -> dict[str, Any]:
        mapping = await cls.get_mapping_to_provider(org_id, data, provider)
        return bend(mapping, data)

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        return {
            field.name: S(field.name) for field in cls.provider_fields() if not is_unset(data.get(field.name, UNSET))
        }

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        return True

    def is_key_valid_for_diff_computation(self, key: str, expected_object: Self) -> bool:
        return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return self.include_field_for_diff_computation(field)

    def include_for_live_patch(self, context: LivePatchContext) -> bool:
        """
        Indicates if this ModelObject should be considered when generating a live patch.

        This method can be overridden if certain object should be ignored depending on their values,
        e.g. secrets that contain only a dummy secret
        """
        return True

    def include_existing_object_for_live_patch(self, org_id: str, parent_object: ModelObject | None) -> bool:
        """
        Indicates if this live ModelObject should be considered when generating a live patch.

        This method can be overridden if certain live objects should be ignored in some cases, e.g. environments
        """
        return True

    def keys(
        self,
        for_diff: bool = False,
        for_patch: bool = False,
        include_model_only_fields: bool = False,
        include_nested_models: bool = False,
        exclude_unset_keys: bool = True,
    ) -> list[str]:
        result = []

        for field in self.model_fields():
            if for_diff is True and not self.include_field_for_diff_computation(field):
                continue

            if for_patch is True and not self.include_field_for_patch_computation(field):
                continue

            if (for_diff or for_patch) and not include_model_only_fields and self.is_model_only(field):
                continue

            if include_nested_models is False and self.is_nested_model(field):
                continue

            if exclude_unset_keys:
                value = self.__getattribute__(field.name)
                if not is_unset(value):
                    result.append(field.name)
            else:
                result.append(field.name)

        return result

    def to_model_dict(
        self,
        for_diff: bool = False,
        include_model_only_fields: bool = False,
        include_nested_models: bool = False,
        exclude_none_values: bool = False,
    ) -> dict[str, Any]:
        result = {}

        for key in self.keys(
            for_diff=for_diff,
            include_model_only_fields=include_model_only_fields,
            include_nested_models=include_nested_models,
            exclude_unset_keys=True,
        ):
            value = self.__getattribute__(key)
            if exclude_none_values and not is_set_and_valid(value):
                continue
            elif self.is_nested_model_key(key):
                result[key] = cast(ModelObject, value).to_model_dict(for_diff, include_nested_models)
            elif self.is_embedded_model_key(key) and is_set_and_valid(value):
                result[key] = cast(EmbeddedModelObject, value).to_model_dict()
            else:
                result[key] = value

        return result

    def requires_web_ui(self) -> bool:
        return False

    def changes_require_web_ui(self, changes: dict[str, Change]) -> bool:
        return False

    def unset_settings_requiring_web_ui(self) -> None:
        return

    def contains_secrets(self) -> bool:
        return False

    def resolve_secrets(self, secret_resolver: Callable[[str], str]) -> None:
        return

    def copy_secrets(self, other_object: ModelObject) -> None:
        return

    def update_dummy_secrets(self, new_value: str) -> None:
        return

    @abstractmethod
    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None: ...

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        jsonnet_config: JsonnetConfig,
        context: PatchContext,
        extend: bool,
        default_object: ModelObject,
    ) -> None:
        patch = self.get_patch_to(default_object)

        template_function = self.get_jsonnet_template_function(jsonnet_config, False)

        if self.is_keyed():
            key = patch.pop(self.get_key())
            printer.print(f"{unwrap(template_function)}('{key}')")
        else:
            printer.print(f"{unwrap(template_function)}")

        write_patch_object_as_json(patch, printer)

    @classmethod
    def generate_live_patch(
        cls: type[MT],
        expected_object: MT | None,
        current_object: MT | None,
        parent_object: ModelObject | None,
        context: LivePatchContext,
        handler: LivePatchHandler,
    ) -> None:
        if current_object is None:
            expected_object = unwrap(expected_object)
            handler(LivePatch.of_addition(expected_object, parent_object, expected_object.apply_live_patch))
            return

        if expected_object is None:
            current_object = unwrap(current_object)
            handler(LivePatch.of_deletion(current_object, parent_object, current_object.apply_live_patch))
            return

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

    @classmethod
    def generate_live_patch_of_list(
        cls,
        expected_objects: Sequence[MT],
        current_objects: Sequence[MT],
        parent_object: MT | None,
        context: LivePatchContext,
        handler: LivePatchHandler,
    ) -> None:
        expected_objects_by_key = associate_by_key(expected_objects, lambda x: x.get_key_value())
        expected_objects_by_all_keys = multi_associate_by_key(expected_objects, lambda x: x.get_all_key_values())

        has_wildcard_keys = any(x.get_key_value().endswith("*") for x in expected_objects)

        for current_object in current_objects:
            key = current_object.get_key_value()

            expected_object = expected_objects_by_all_keys.get(key)
            if expected_object is None and has_wildcard_keys:
                for obj in expected_objects:
                    stripped_key = obj.get_key_value().rstrip("*")
                    if stripped_key and key.startswith(stripped_key):
                        expected_object = obj
                        break

            if expected_object is None:
                if current_object.include_existing_object_for_live_patch(context.org_id, parent_object):
                    cls.generate_live_patch(None, current_object, parent_object, context, handler)
                continue

            if expected_object.include_for_live_patch(context):
                cls.generate_live_patch(expected_object, current_object, parent_object, context, handler)

            for k in expected_object.get_all_key_values():
                expected_objects_by_all_keys.pop(k)
            expected_objects_by_key.pop(expected_object.get_key_value())

        for _, expected_object in expected_objects_by_key.items():
            if expected_object.include_for_live_patch(context):
                cls.generate_live_patch(expected_object, None, parent_object, context, handler)

    @classmethod
    @abstractmethod
    async def apply_live_patch(cls: type[MT], patch: LivePatch[MT], org_id: str, provider: GitHubProvider) -> None: ...
