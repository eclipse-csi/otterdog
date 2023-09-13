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
from typing import Any, Optional, cast, Callable

from jsonbender import bend, S, OptionalS  # type: ignore

from otterdog.models import ModelObject, ValidationContext, FailureType
from otterdog.providers.github import GitHubProvider
from otterdog.utils import UNSET, is_unset, is_set_and_valid, is_set_and_present


@dataclasses.dataclass
class Webhook(ModelObject, abc.ABC):
    """
    Represents a Webhook.
    """

    id: int = dataclasses.field(metadata={"external_only": True})
    events: list[str]
    active: bool
    url: str = dataclasses.field(metadata={"key": True})
    content_type: str
    insecure_ssl: str
    secret: Optional[str]

    # model only fields
    aliases: list[str] = dataclasses.field(metadata={"model_only": True}, default_factory=list)

    def get_all_urls(self) -> list[str]:
        return [self.url] + self.aliases

    def has_dummy_secret(self) -> bool:
        if is_set_and_valid(self.secret) and all(ch == "*" for ch in self.secret):  # type: ignore
            return True
        else:
            return False

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        match field.name:
            case "secret":
                return False
            case _:
                return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        if self.has_dummy_secret():
            context.add_failure(
                FailureType.INFO,
                f"{self.get_model_header(parent_object)} will be skipped during processing:\n"
                f"webhook has a secret set, but only a dummy secret '{self.secret}' is provided in "
                f"the configuration.",
            )
        elif is_set_and_present(self.secret) and ":" not in self.secret:
            context.add_failure(
                FailureType.WARNING,
                f"{self.get_model_header()} has a secret '{self.secret}' that does not use a credential provider.",
            )

        if is_set_and_valid(self.content_type):
            if self.content_type not in {"json", "form"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"'content_type' has value '{self.content_type}', " f"only values ('json' | 'form') are allowed.",
                )

        if is_set_and_valid(self.insecure_ssl):
            if self.insecure_ssl not in {"0", "1"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"'insecure_ssl' has value '{self.insecure_ssl}', " f"only values ('0' | '1') are allowed.",
                )

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
        mapping.update(
            {
                "url": OptionalS("config", "url", default=UNSET),
                "content_type": OptionalS("config", "content_type", default=UNSET),
                "insecure_ssl": OptionalS("config", "insecure_ssl", default=UNSET),
                "secret": OptionalS("config", "secret", default=None),
            }
        )
        return mapping

    @classmethod
    def get_mapping_to_provider(cls, org_id: str, data: dict[str, Any], provider: GitHubProvider) -> dict[str, Any]:
        mapping = {
            field.name: S(field.name) for field in cls.provider_fields() if not is_unset(data.get(field.name, UNSET))
        }

        config_mapping = {}
        for config_prop in ["url", "content_type", "insecure_ssl", "secret"]:
            if config_prop in mapping:
                mapping.pop(config_prop)
                config_mapping[config_prop] = S(config_prop)

        if len(config_mapping) > 0:
            mapping["config"] = config_mapping

        return mapping

    def resolve_secrets(self, secret_resolver: Callable[[str], str]) -> None:
        webhook_secret = self.secret
        if not is_unset(webhook_secret) and webhook_secret is not None:
            self.secret = secret_resolver(webhook_secret)

    def copy_secrets(self, other_object: ModelObject) -> None:
        if self.has_dummy_secret():
            self.secret = cast(Webhook, other_object).secret
