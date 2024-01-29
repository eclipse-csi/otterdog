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

from jsonbender import OptionalS, S, bend  # type: ignore

from otterdog.models import (
    FailureType,
    LivePatch,
    LivePatchContext,
    LivePatchHandler,
    ModelObject,
    ValidationContext,
)
from otterdog.providers.github import GitHubProvider
from otterdog.utils import UNSET, Change, is_set_and_present, is_set_and_valid, is_unset

WT = TypeVar("WT", bound="Webhook")


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

    def get_all_key_values(self) -> list[Any]:
        return self.get_all_urls()

    def has_dummy_secret(self) -> bool:
        if is_set_and_valid(self.secret) and all(ch == "*" for ch in self.secret):  # type: ignore
            return True
        else:
            return False

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        return self.is_key_valid_for_diff_computation(field.name)

    def is_key_valid_for_diff_computation(self, key: str) -> bool:
        if key == "secret":
            return not self.has_dummy_secret()
        else:
            return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

    def include_for_live_patch(self) -> bool:
        return not self.has_dummy_secret()

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
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping: dict[str, Any] = {
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

    def contains_secrets(self) -> bool:
        return self.secret is not None

    def resolve_secrets(self, secret_resolver: Callable[[str], str]) -> None:
        webhook_secret = self.secret
        if not is_unset(webhook_secret) and webhook_secret is not None:
            self.secret = secret_resolver(webhook_secret)

    def copy_secrets(self, other_object: ModelObject) -> None:
        if self.has_dummy_secret():
            self.secret = cast(Webhook, other_object).secret

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
            assert isinstance(expected_object, Webhook)
            handler(LivePatch.of_addition(expected_object, parent_object, expected_object.apply_live_patch))
            return

        if expected_object is None:
            assert isinstance(current_object, Webhook)
            handler(LivePatch.of_deletion(current_object, parent_object, current_object.apply_live_patch))
            return

        assert isinstance(expected_object, Webhook)
        assert isinstance(current_object, Webhook)

        # if webhooks shall be updated and the webhook contains a valid secret perform a forced update.
        if (
            context.update_webhooks
            and is_set_and_valid(expected_object.secret)
            and re.match(context.update_filter, expected_object.url)
        ):
            model_dict = expected_object.to_model_dict()
            modified_webhook: dict[str, Change[Any]] = {k: Change(v, v) for k, v in model_dict.items()}

            handler(
                LivePatch.of_changes(
                    expected_object,
                    current_object,
                    modified_webhook,
                    parent_object,
                    True,
                    expected_object.apply_live_patch,
                )
            )
            return

        modified_webhook = expected_object.get_difference_from(current_object)

        if not is_unset(expected_object.secret):
            # special handling for secrets:
            #   if a secret was present by now its gone or vice-versa,
            #   include it in the diff view.
            expected_secret = expected_object.secret
            current_secret = current_object.secret

            def has_valid_secret(webhook: Webhook):
                return webhook.secret is not None and not webhook.has_dummy_secret()

            # if there are different unresolved secrets, display changes
            has_different_unresolved_secrets = (
                has_valid_secret(expected_object)
                and has_valid_secret(current_object)
                and expected_secret != current_secret
            )

            if (
                (expected_secret is not None and current_secret is None)
                or (expected_secret is None and current_secret is not None)
                or has_different_unresolved_secrets
            ):
                modified_webhook["secret"] = Change(current_secret, expected_secret)

        if len(modified_webhook) > 0:
            handler(
                LivePatch.of_changes(
                    expected_object,
                    current_object,
                    modified_webhook,
                    parent_object,
                    False,
                    expected_object.apply_live_patch,
                )
            )
