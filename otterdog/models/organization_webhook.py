# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import Any, Optional

from jsonbender import bend, S, OptionalS

from otterdog.providers.github import Github
from otterdog.utils import UNSET, is_unset, is_set_and_valid
from . import ModelObject, ValidationContext, FailureType


@dataclasses.dataclass
class OrganizationWebhook(ModelObject):
    id: str = dataclasses.field(metadata={"external_only": True})
    events: list[str]
    active: bool
    url: str = dataclasses.field(metadata={"key": True})
    content_type: str
    insecure_ssl: str
    secret: Optional[str]

    def validate(self, context: ValidationContext, parent_object: object) -> None:
        if is_set_and_valid(self.secret) and all(ch == '*' for ch in self.secret):
            context.add_failure(FailureType.ERROR,
                                f"webhook with url '{self.url}' uses a dummy secret '{self.secret}', "
                                f"provide a real secret using a credential provider.")

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        match field.name:
            case "secret": return False
            case _: return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

    @classmethod
    def from_model(cls, data: dict[str, Any]) -> OrganizationWebhook:
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        return cls(**bend(mapping, data))

    @classmethod
    def from_provider(cls, data: dict[str, Any]) -> OrganizationWebhook:
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        mapping.update(
            {
                "url": OptionalS("config", "url", default=UNSET),
                "content_type": OptionalS("config", "content_type", default=UNSET),
                "insecure_ssl": OptionalS("config", "insecure_ssl", default=UNSET),
                "secret": OptionalS("config", "secret", default=None)
            }
        )
        return cls(**bend(mapping, data))

    @classmethod
    def _to_provider(cls, data: dict[str, Any], provider: Optional[Github] = None) -> dict[str, Any]:
        mapping = {field.name: S(field.name) for field in cls.provider_fields() if
                   not is_unset(data.get(field.name, UNSET))}

        config_mapping = {}
        for config_prop in ["url", "content_type", "insecure_ssl", "secret"]:
            if config_prop in mapping:
                mapping.pop(config_prop)
                config_mapping[config_prop] = S(config_prop)

        if len(config_mapping) > 0:
            mapping["config"] = config_mapping

        return bend(mapping, data)
