# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from dataclasses import dataclass, field
from typing import Any

from jsonbender import bend, S, OptionalS

from . import ModelObject, UNSET


@dataclass
class OrganizationWebhook(ModelObject):
    id: str = field(metadata={"external_only": True})
    events: list[str]
    active: bool
    url: str = field(metadata={"key": True})
    content_type: str
    insecure_ssl: str
    secret: str

    @classmethod
    def from_model(cls, data: dict[str, Any]) -> "OrganizationWebhook":
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        return cls(**bend(mapping, data))

    @classmethod
    def from_provider(cls, data: dict[str, Any]) -> "OrganizationWebhook":
        mapping = {k: S(k) for k in map(lambda x: x.name, cls.all_fields())}
        mapping.update({"secret": OptionalS("config", "secret", default=UNSET)})
        return cls(**bend(mapping, data))
