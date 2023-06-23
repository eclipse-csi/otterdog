# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import Any, cast

from jsonbender import bend, S, OptionalS, K, Forall, If  # type: ignore

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import ModelObject, ValidationContext, FailureType
from otterdog.models.secret import Secret
from otterdog.providers.github import Github
from otterdog.utils import IndentingPrinter, write_patch_object_as_json, is_unset, is_set_and_valid, UNSET


@dataclasses.dataclass
class OrganizationSecret(Secret):
    """
    Represents a Secret defined on organization level.
    """

    visibility: str
    selected_repositories: list[str]

    @property
    def model_object_name(self) -> str:
        return "org_secret"

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        super().validate(context, parent_object)

        if is_set_and_valid(self.visibility):
            from .github_organization import GitHubOrganization
            org = cast(GitHubOrganization, parent_object)
            if self.visibility == "private" and org.settings.plan == "free":
                context.add_failure(FailureType.ERROR,
                                    f"{self.get_model_header(parent_object)} has 'visibility' of value "
                                    f"'{self.visibility}' which is not available for organization with free plan.")
            elif self.visibility not in {"public", "private", "selected"}:
                context.add_failure(FailureType.ERROR,
                                    f"{self.get_model_header(parent_object)} has 'visibility' of value "
                                    f"'{self.visibility}', "
                                    f"only values ('public' | 'private' | 'selected') are allowed.")

            if self.visibility != "selected" and len(self.selected_repositories) > 0:
                context.add_failure(FailureType.WARNING,
                                    f"{self.get_model_header(parent_object)} has 'visibility' set to "
                                    f"'{self.visibility}', "
                                    f"but 'selected_repositories' is set to '{self.selected_repositories}', "
                                    f"setting will be ignored.")

    @classmethod
    def from_provider_data(cls, org_id: str, data: dict[str, Any]):
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}
        mapping.update(
            {
                "visibility": If(S("visibility") == K("all"),
                                 K("public"),
                                 OptionalS("visibility", default=UNSET)),

                "selected_repositories":
                    OptionalS("selected_repositories", default=[]) >>
                    Forall(lambda x: x["name"]),

                # the provider will never send the value itself, use a dummy secret.
                "value": K("********")
            }
        )
        return cls(**bend(mapping, data))

    @classmethod
    def _to_provider_data(cls, org_id: str, data: dict[str, Any], provider: Github) -> dict[str, Any]:
        assert provider is not None

        mapping = {field.name: S(field.name) for field in cls.provider_fields() if
                   not is_unset(data.get(field.name, UNSET))}

        if "value" in mapping:
            mapping.pop("value")

            key_id, public_key = provider.get_org_public_key(org_id)
            mapping["encrypted_value"] = K(Secret.encrypt_value(public_key, data["value"]))
            mapping["key_id"] = K(key_id)

        if "visibility" in mapping:
            mapping["visibility"] = If(S("visibility") == K("public"), K("all"), S("visibility"))

        if "selected_repositories" in mapping:
            mapping.pop("selected_repositories")
            mapping["selected_repository_ids"] = K(provider.get_repo_ids(org_id, data["selected_repositories"]))

        return bend(mapping, data)

    def to_jsonnet(self,
                   printer: IndentingPrinter,
                   jsonnet_config: JsonnetConfig,
                   extend: bool,
                   default_object: ModelObject) -> None:
        patch = self.get_patch_to(default_object)
        patch.pop("name")
        printer.print(f"orgs.{jsonnet_config.create_org_secret}('{self.name}')")
        write_patch_object_as_json(patch, printer)
