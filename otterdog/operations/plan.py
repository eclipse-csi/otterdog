#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from typing import Any, Optional

from otterdog.config import OtterdogConfig
from otterdog.models import LivePatch, ModelObject
from otterdog.models.webhook import Webhook
from otterdog.utils import Change, IndentingPrinter, style

from .diff_operation import DiffOperation, DiffStatus


class PlanOperation(DiffOperation):
    """
    Calculates and displays changes that would be applied to an organization based on the current configuration.
    """

    def __init__(self, no_web_ui: bool, update_webhooks: bool, update_secrets: bool, update_filter: str):
        super().__init__(no_web_ui, update_webhooks, update_secrets, update_filter)

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        super().init(config, printer)

    def pre_execute(self) -> None:
        self.printer.println("Planning execution:")
        self.print_legend()

    def print_legend(self) -> None:
        self.printer.println("\nActions are indicated with the following symbols:")
        self.printer.println(f"  {style('+', fg='green')} create")
        self.printer.println(f"  {style('~', fg='yellow')} modify")
        self.printer.println(f"  {style('!', fg='magenta')} forced update")
        self.printer.println(f"  {style('-', fg='red')} delete")

    def resolve_secrets(self) -> bool:
        return False

    def handle_add_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: Optional[ModelObject] = None,
    ) -> None:
        self.printer.println()
        model_header = model_object.get_model_header(parent_object)
        self.print_dict(
            model_object.to_model_dict(for_diff=True),
            f"add {model_header}",
            "+",
            "green",
        )

    def handle_delete_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: Optional[ModelObject] = None,
    ) -> None:
        self.printer.println()
        model_header = model_object.get_model_header(parent_object)
        self.print_dict(
            model_object.to_model_dict(for_diff=True),
            f"remove {model_header}",
            "-",
            "red",
        )

    def handle_modified_object(
        self,
        org_id: str,
        modified_object: dict[str, Change[Any]],
        forced_update: bool,
        current_object: ModelObject,
        expected_object: ModelObject,
        parent_object: Optional[ModelObject] = None,
    ) -> int:
        self.printer.println()
        model_header = current_object.get_model_header(parent_object)
        self.print_modified_dict(modified_object, model_header, set(), forced_update)

        # FIXME: this code should be moved to the Webhook model class.
        if isinstance(current_object, Webhook):
            if "secret" in modified_object:
                new_secret = modified_object["secret"].to_value
                if not new_secret:
                    self.printer.println(
                        f"\n{style('Warning', fg='red')}: removing secret for webhook "
                        f"with url '{current_object.url}'"
                    )

        settings_to_change = 0
        for k, v in modified_object.items():
            if current_object.is_read_only_key(k):
                self.printer.println(
                    f"\n{style('Note', fg='yellow')}: setting '{k}' " f"is read-only, will be skipped."
                )
            else:
                settings_to_change += 1

        return settings_to_change

    async def handle_finish(self, org_id: str, diff_status: DiffStatus, patches: list[LivePatch]) -> None:
        self.printer.println(
            f"\n{style('Plan', bright=True)}: {diff_status.additions} to add, "
            f"{diff_status.differences} to change, "
            f"{diff_status.deletions} to delete."
        )
