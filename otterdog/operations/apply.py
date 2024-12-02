#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from otterdog.models import LivePatch, LivePatchType
from otterdog.utils import Change, IndentingPrinter, get_approval

from .plan import PlanOperation

if TYPE_CHECKING:
    from typing import Any

    from otterdog.config import OrganizationConfig, OtterdogConfig
    from otterdog.models import ModelObject

    from .diff_operation import DiffStatus


class ApplyOperation(PlanOperation):
    def __init__(
        self,
        force_processing: bool,
        no_web_ui: bool,
        repo_filter: str,
        update_webhooks: bool,
        update_secrets: bool,
        update_filter: str,
        delete_resources: bool,
        resolve_secrets: bool = True,
        include_resources_with_secrets: bool = True,
    ):
        super().__init__(no_web_ui, repo_filter, update_webhooks, update_secrets, update_filter)
        self._force_processing = force_processing
        self._delete_resources = delete_resources
        self._resolve_secrets = resolve_secrets
        self._include_resources_with_secrets = include_resources_with_secrets

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        super().init(config, printer)

    def pre_execute(self) -> None:
        self.printer.println("Applying changes:")
        self.print_legend()

    def include_resources_with_secrets(self) -> bool:
        return self._include_resources_with_secrets

    def resolve_secrets(self) -> bool:
        return self._resolve_secrets

    def handle_add_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: ModelObject | None = None,
    ) -> None:
        super().handle_add_object(org_id, model_object, parent_object)
        self.execute_custom_hook_if_present_with_model_object(self.org_config, model_object, "pre-add-object-hook.py")

    def handle_delete_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: ModelObject | None = None,
    ) -> None:
        super().handle_delete_object(org_id, model_object, parent_object)

    def handle_modified_object(
        self,
        org_id: str,
        modified_object: dict[str, Change[Any]],
        forced_update: bool,
        current_object: ModelObject,
        expected_object: ModelObject,
        parent_object: ModelObject | None = None,
    ) -> int:
        modified = super().handle_modified_object(
            org_id,
            modified_object,
            forced_update,
            current_object,
            expected_object,
            parent_object,
        )
        return modified

    async def handle_finish(self, org_id: str, diff_status: DiffStatus, patches: list[LivePatch]) -> int:
        self.printer.println()

        if diff_status.total_changes(self._delete_resources) == 0:
            self.printer.println("No changes required.")
            if not self._delete_resources and diff_status.deletions > 0:
                self.printer.println(
                    f"{diff_status.deletions} resource(s) would be deleted with flag '--delete-resources'."
                )
            return 0

        if not self._force_processing:
            if diff_status.deletions > 0 and not self._delete_resources:
                self.printer.println("No resource will be removed, use flag '--delete-resources' to delete them.\n")

            self.printer.println(
                "Do you want to perform these actions? (Only 'yes' or 'y' will be accepted to approve)\n"
            )

            self.printer.print("[bold]Enter a value:[/] ")
            if not get_approval():
                self.printer.println("\nApply cancelled.")
                return 0

        # apply patches
        from rich.progress import Progress

        errors = 0

        self.printer.println("\nApplying changes:")

        # order patches by readonly status:
        # - first: the patches that do not make a resource readonly
        # - second: remaining patches
        # this is necessary as readonly resources can't be modified afterward, so we perform first
        # any necessary modification on them, and make them readonly at the end
        patches_ordered_by_readonly_status = [p for p in patches if p.changes_object_to_readonly is False] + [
            p for p in patches if p.changes_object_to_readonly is True
        ]

        with Progress(console=self.printer.console) as progress:
            task = progress.add_task(self.printer.current_indentation, total=len(patches_ordered_by_readonly_status))
            for patch in patches_ordered_by_readonly_status:
                if patch.patch_type == LivePatchType.REMOVE and not self._delete_resources:
                    progress.advance(task)
                    continue
                else:
                    try:
                        await patch.apply(org_id, self.gh_client)
                    except RuntimeError as ex:
                        errors += 1
                        self.printer.println()
                        self.printer.print_error(f"failed to apply patch: {patch!r}\n{ex}")
                    finally:
                        progress.advance(task)

        delete_snippet = "deleted" if self._delete_resources else "live resources ignored"

        self.printer.println("\nDone.")

        self.printer.println(
            f"\n[bold]Executed plan:[/] {diff_status.additions} added, "
            f"{diff_status.differences} changed, "
            f"{diff_status.deletions} {delete_snippet}.",
            highlight=True,
        )

        add_patches = [p for p in patches if p.patch_type == LivePatchType.ADD]
        if len(add_patches) > 0:
            self.execute_custom_hook_if_present_with_patches(self.org_config, add_patches, "post-add-objects-hook.py")

        return errors

    def execute_custom_hook_if_present_with_model_object(
        self, org_config: OrganizationConfig, model_object: ModelObject, filename: str
    ) -> None:
        import os

        hook_script = os.path.join(self.template_dir, filename)
        if os.path.exists(hook_script):
            with open(hook_script) as file:
                exec(file.read())

    def execute_custom_hook_if_present_with_patches(
        self, org_config: OrganizationConfig, patches: list[LivePatch], filename: str
    ) -> None:
        import os

        hook_script = os.path.join(self.template_dir, filename)
        if os.path.exists(hook_script):
            with open(hook_script) as file:
                exec(file.read())
