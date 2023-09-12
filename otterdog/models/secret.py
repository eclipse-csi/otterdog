# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

import abc
import dataclasses
from typing import Any, cast, Callable

from jsonbender import bend, S, OptionalS, K  # type: ignore

from otterdog.models import ModelObject, ValidationContext, FailureType
from otterdog.providers.github import GitHubProvider
from otterdog.utils import UNSET, is_unset, is_set_and_valid


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
        match field.name:
            case "value":
                return False
            case _:
                return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

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
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        # the provider will never send the value itself, use a dummy secret.
        mapping["value"] = K("********")
        return mapping

    @classmethod
    def get_mapping_to_provider(cls, org_id: str, data: dict[str, Any], provider: GitHubProvider) -> dict[str, Any]:
        return {
            field.name: S(field.name) for field in cls.provider_fields() if not is_unset(data.get(field.name, UNSET))
        }

    def resolve_secrets(self, secret_resolver: Callable[[str], str]) -> None:
        secret_value = self.value
        if not is_unset(secret_value) and secret_value is not None:
            self.value = secret_resolver(secret_value)

    def copy_secrets(self, other_object: ModelObject) -> None:
        if self.has_dummy_secret():
            self.value = cast(Secret, other_object).value
