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
from otterdog.models import ModelObject
from otterdog.models.secret import Secret
from otterdog.utils import IndentingPrinter, write_patch_object_as_json


@dataclasses.dataclass
class RepositorySecret(Secret):
    """
    Represents a Secret defined on repo level.
    """

    @property
    def model_object_name(self) -> str:
        return "repo_secret"

    def to_jsonnet(self,
                   printer: IndentingPrinter,
                   jsonnet_config: JsonnetConfig,
                   extend: bool,
                   default_object: ModelObject) -> None:
        patch = self.get_patch_to(default_object)
        patch.pop("name")
        printer.print(f"orgs.{jsonnet_config.create_repo_secret}('{self.name}')")
        write_patch_object_as_json(patch, printer)
