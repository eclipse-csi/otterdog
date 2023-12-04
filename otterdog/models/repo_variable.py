# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

import dataclasses

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import ModelObject, LivePatch, LivePatchType
from otterdog.models.variable import Variable
from otterdog.providers.github import GitHubProvider
from otterdog.utils import IndentingPrinter, write_patch_object_as_json


@dataclasses.dataclass
class RepositoryVariable(Variable):
    """
    Represents a Variable defined on repo level.
    """

    @property
    def model_object_name(self) -> str:
        return "repo_variable"

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        jsonnet_config: JsonnetConfig,
        extend: bool,
        default_object: ModelObject,
    ) -> None:
        patch = self.get_patch_to(default_object)
        patch.pop("name")
        printer.print(f"orgs.{jsonnet_config.create_repo_variable}('{self.name}')")
        write_patch_object_as_json(patch, printer)

    @classmethod
    def apply_live_patch(cls, patch: LivePatch, org_id: str, provider: GitHubProvider) -> None:
        from .repository import Repository

        match patch.patch_type:
            case LivePatchType.ADD:
                assert isinstance(patch.expected_object, RepositoryVariable)
                assert isinstance(patch.parent_object, Repository)
                provider.add_repo_variable(
                    org_id, patch.parent_object.name, patch.expected_object.to_provider_data(org_id, provider)
                )

            case LivePatchType.REMOVE:
                assert isinstance(patch.current_object, RepositoryVariable)
                assert isinstance(patch.parent_object, Repository)
                provider.delete_repo_variable(org_id, patch.parent_object.name, patch.current_object.name)

            case LivePatchType.CHANGE:
                assert isinstance(patch.expected_object, RepositoryVariable)
                assert isinstance(patch.current_object, RepositoryVariable)
                assert isinstance(patch.parent_object, Repository)
                provider.update_repo_variable(
                    org_id,
                    patch.parent_object.name,
                    patch.current_object.name,
                    patch.expected_object.to_provider_data(org_id, provider),
                )
