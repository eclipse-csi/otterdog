#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from otterdog.models.webhook import Webhook

from .diff_operation import DiffOperation, DiffStatus

if TYPE_CHECKING:
    from typing import Any

    from otterdog.config import OtterdogConfig
    from otterdog.models import LivePatch, ModelObject
    from otterdog.utils import Change, IndentingPrinter


class PlanOperation(DiffOperation):
    """
    Calculates and displays changes that would be applied to an organization based on the current configuration.
    """

    def __init__(
        self,
        no_web_ui: bool,
        repo_filter: str,
        update_webhooks: bool,
        update_secrets: bool,
        update_filter: str,
    ):
        super().__init__(no_web_ui, repo_filter, update_webhooks, update_secrets, update_filter)

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        super().init(config, printer)

    def pre_execute(self) -> None:
        self.printer.println("Planning execution:")
        self.print_legend()

    def print_legend(self) -> None:
        self.printer.println("\nActions are indicated with the following symbols:")
        self.printer.println("  [green]+[/] create")
        self.printer.println("  [yellow]~[/] modify")
        self.printer.println("  [magenta]![/] forced update")
        self.printer.println("  [red]-[/] delete")

    def resolve_secrets(self) -> bool:
        return False

    def handle_add_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: ModelObject | None = None,
    ) -> None:
        self.printer.println()
        model_header = model_object.get_model_header(parent_object)
        self.print_dict(
            model_object.to_model_dict(for_diff=True, include_model_only_fields=True, exclude_none_values=True),
            f"add {model_header}",
            "+",
            "green",
        )

    def handle_delete_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: ModelObject | None = None,
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
        parent_object: ModelObject | None = None,
    ) -> int:
        self.printer.println()
        model_header = expected_object.get_model_header(parent_object)
        self.print_modified_dict(modified_object, model_header, forced_update)

        # FIXME: this code should be moved to the Webhook model class.
        if isinstance(current_object, Webhook):
            if "secret" in modified_object:
                new_secret = modified_object["secret"].to_value
                if not new_secret:
                    self.printer.println(
                        f"\n[red]Warning[/]: removing secret for webhook with url '{current_object.url}'"
                    )

        settings_to_change = 0
        for k, _v in modified_object.items():
            if current_object.is_read_only_key(k):
                self.printer.println(f"\n[yellow]Note[/]: setting '{k}' is read-only, will be skipped.")
            else:
                settings_to_change += 1

        return settings_to_change

    async def handle_finish(self, org_id: str, diff_status: DiffStatus, patches: list[LivePatch]) -> int:
        self.printer.println(
            f"\n[bold]Plan[/]: {diff_status.additions} to add, "
            f"{diff_status.differences} to change, "
            f"{diff_status.deletions} to delete.",
            highlight=True,
        )

        return 0
