#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import abc
import dataclasses
import re
from typing import Any, Callable, Optional, TypeVar, cast

from jsonbender import K, OptionalS, S, bend  # type: ignore

from otterdog.models import (
    FailureType,
    LivePatch,
    LivePatchContext,
    LivePatchHandler,
    ModelObject,
    ValidationContext,
)
from otterdog.providers.github import GitHubProvider
from otterdog.utils import UNSET, Change, is_set_and_valid, is_unset

ST = TypeVar("ST", bound="Secret")


@dataclasses.dataclass
class Secret(ModelObject, abc.ABC):
    """
    Represents a Secret.
    """

    name: str = dataclasses.field(metadata={"key": True})
    value: str

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        if self.has_dummy_secret():
            context.add_failure(
                FailureType.INFO,
                f"{self.get_model_header()} will be skipped during processing:\n"
                f"only a dummy value '{self.value}' is provided in the configuration.",
            )
        else:
            if ":" not in self.value:
                context.add_failure(
                    FailureType.WARNING,
                    f"{self.get_model_header()} has a value '{self.value}' that does not use a credential provider.",
                )

        if self.name.startswith("GITHUB_"):
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header()} starts with prefix 'GITHUB_' which is not allowed for secrets.",
            )

    def has_dummy_secret(self) -> bool:
        if is_set_and_valid(self.value) and all(ch == "*" for ch in self.value):  # type: ignore
            return True
        else:
            return False

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        return self.is_key_valid_for_diff_computation(field.name)

    def is_key_valid_for_diff_computation(self, key: str) -> bool:
        if key == "value":
            return not self.has_dummy_secret()
        else:
            return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

    def include_for_live_patch(self) -> bool:
        return not self.has_dummy_secret()

    @classmethod
    def from_model_data(cls, data: dict[str, Any]):
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        return cls(**bend(mapping, data))

    @classmethod
    def from_provider_data(cls, org_id: str, data: dict[str, Any]):
        mapping = cls.get_mapping_from_provider(org_id, data)
        return cls(**bend(mapping, data))

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping: dict[str, Any] = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        # the provider will never send the value itself, use a dummy secret.
        mapping["value"] = K("********")
        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        return {
            field.name: S(field.name) for field in cls.provider_fields() if not is_unset(data.get(field.name, UNSET))
        }

    def contains_secrets(self) -> bool:
        return True

    def resolve_secrets(self, secret_resolver: Callable[[str], str]) -> None:
        secret_value = self.value
        if not is_unset(secret_value) and secret_value is not None:
            self.value = secret_resolver(secret_value)

    def copy_secrets(self, other_object: ModelObject) -> None:
        if self.has_dummy_secret():
            self.value = cast(Secret, other_object).value

    @classmethod
    def generate_live_patch(
        cls,
        expected_object: Optional[ModelObject],
        current_object: Optional[ModelObject],
        parent_object: Optional[ModelObject],
        context: LivePatchContext,
        handler: LivePatchHandler,
    ) -> None:
        if current_object is None:
            assert isinstance(expected_object, Secret)
            handler(LivePatch.of_addition(expected_object, parent_object, expected_object.apply_live_patch))
            return

        if expected_object is None:
            assert isinstance(current_object, Secret)
            handler(LivePatch.of_deletion(current_object, parent_object, current_object.apply_live_patch))
            return

        assert isinstance(expected_object, Secret)
        assert isinstance(current_object, Secret)

        # if secrets shall be updated and the secret contains a valid secret perform a forced update.
        if context.update_secrets and re.match(context.update_filter, expected_object.name):
            model_dict = expected_object.to_model_dict()
            modified_secret: dict[str, Change[Any]] = {k: Change(v, v) for k, v in model_dict.items()}

            handler(
                LivePatch.of_changes(
                    expected_object,
                    current_object,
                    modified_secret,
                    parent_object,
                    True,
                    expected_object.apply_live_patch,
                )
            )
            return

        modified_secret = expected_object.get_difference_from(current_object)

        if not is_unset(expected_object.value):
            expected_secret_value = expected_object.value
            current_secret_value = current_object.value

            def has_valid_secret(secret: Secret):
                return secret.value is not None and not secret.has_dummy_secret()

            # if there are different unresolved secrets, display changes
            if (
                has_valid_secret(expected_object)
                and has_valid_secret(current_object)
                and expected_secret_value != current_secret_value
            ):
                modified_secret["value"] = Change(current_secret_value, expected_secret_value)

        if len(modified_secret) > 0:
            handler(
                LivePatch.of_changes(
                    expected_object,
                    current_object,
                    modified_secret,
                    parent_object,
                    False,
                    expected_object.apply_live_patch,
                )
            )
