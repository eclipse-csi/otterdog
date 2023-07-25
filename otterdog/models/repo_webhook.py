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
from otterdog.models.webhook import Webhook
from otterdog.utils import IndentingPrinter, write_patch_object_as_json


@dataclasses.dataclass
class RepositoryWebhook(Webhook):
    """
    Represents a Webhook defined on repo level.
    """

    @property
    def model_object_name(self) -> str:
        return "repo_webhook"

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        jsonnet_config: JsonnetConfig,
        extend: bool,
        default_object: ModelObject,
    ) -> None:
        patch = self.get_patch_to(default_object)
        patch.pop("url")
        printer.print(f"orgs.{jsonnet_config.create_repo_webhook}('{self.url}')")
        write_patch_object_as_json(patch, printer)
