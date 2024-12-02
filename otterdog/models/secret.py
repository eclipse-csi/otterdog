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
import fnmatch
import re
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from jsonbender import K  # type: ignore

from otterdog.models import (
    FailureType,
    LivePatch,
    LivePatchContext,
    LivePatchHandler,
    ModelObject,
    ValidationContext,
)
from otterdog.utils import Change, is_set_and_present, is_unset, unwrap

if TYPE_CHECKING:
    from collections.abc import Callable


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
                FailureType.INFO, f"{self.get_model_header()} only has a dummy value, resource will be skipped."
            )
        else:
            if ":" in self.value:
                provider_type, _ = re.split(":", self.value)
                resolved_secret = context.secret_resolver.is_supported_secret_provider(provider_type)
            else:
                resolved_secret = False

            if resolved_secret is False:
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
        if is_set_and_present(self.value) and len(self.value) > 0 and all(ch == "*" for ch in self.value):
            return True
        return False

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        if field.name == "value":
            return not self.has_dummy_secret()
        return True

    def is_key_valid_for_diff_computation(self, key: str, expected_object: Self) -> bool:
        if key == "value":
            return not self.has_dummy_secret()
        return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

    def include_for_live_patch(self, context: LivePatchContext) -> bool:
        return not self.has_dummy_secret()

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)
        # the provider will never send the value itself, use a dummy secret.
        mapping["value"] = K("********")
        return mapping

    def contains_secrets(self) -> bool:
        return True

    def resolve_secrets(self, secret_resolver: Callable[[str], str]) -> None:
        secret_value = self.value
        if not is_unset(secret_value) and secret_value is not None:
            self.value = secret_resolver(secret_value)

    def copy_secrets(self, other_object: ModelObject) -> None:
        if self.has_dummy_secret():
            self.value = cast(Secret, other_object).value

    def update_dummy_secrets(self, new_value: str) -> None:
        if self.has_dummy_secret():
            self.value = new_value

    @classmethod
    def generate_live_patch(
        cls,
        expected_object: ST | None,
        current_object: ST | None,
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

        # if secrets shall be updated and the secret contains a valid secret perform a forced update.
        if context.update_secrets and fnmatch.fnmatch(expected_object.name, context.update_filter):
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
