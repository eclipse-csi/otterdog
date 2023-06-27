# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import Any

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import ValidationContext, FailureType, ModelObject
from otterdog.models.webhook import Webhook
from otterdog.utils import IndentingPrinter, write_patch_object_as_json


@dataclasses.dataclass
class OrganizationWebhook(Webhook):
    """
    Represents a Webhook defined on organization level.
    """

    @property
    def model_object_name(self) -> str:
        return "org_webhook"

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        if self.has_dummy_secret():
            context.add_failure(
                FailureType.INFO,
                f"{self.get_model_header()} will be skipped during processing:\n"
                f"webhook has a secret set, but only a dummy secret '{self.secret}' is provided in "
                f"the configuration.",
            )

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        jsonnet_config: JsonnetConfig,
        extend: bool,
        default_object: ModelObject,
    ) -> None:
        patch = self.get_patch_to(default_object)
        patch.pop("url")
        printer.print(f"orgs.{jsonnet_config.create_org_webhook}('{self.url}')")
        write_patch_object_as_json(patch, printer)
