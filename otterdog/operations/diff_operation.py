#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

import aiofiles.ospath

from otterdog.models import LivePatch, LivePatchContext, LivePatchType
from otterdog.models.github_organization import GitHubOrganization
from otterdog.providers.github import GitHubProvider
from otterdog.utils import Change, IndentingPrinter, unwrap

from . import Operation
from .validate import ValidateOperation

if TYPE_CHECKING:
    from typing import Any

    from otterdog.config import OrganizationConfig, OtterdogConfig
    from otterdog.jsonnet import JsonnetConfig
    from otterdog.models import ModelObject


class DiffStatus:
    def __init__(self):
        self.additions = 0
        self.differences = 0
        self.deletions = 0

    def total_changes(self, include_deletions: bool) -> int:
        if include_deletions:
            return self.additions + self.differences + self.deletions
        else:
            return self.additions + self.differences


class CallbackFn(Protocol):
    def __call__(self, org_id: str, diff_status: DiffStatus, patches: list[LivePatch]) -> None: ...


class DiffOperation(Operation):
    def __init__(
        self,
        no_web_ui: bool,
        repo_filter: str,
        update_webhooks: bool,
        update_secrets: bool,
        update_filter: str,
    ):
        super().__init__()

        self.no_web_ui = no_web_ui
        self.repo_filter = repo_filter
        self.update_webhooks = update_webhooks
        self.update_secrets = update_secrets
        self.update_filter = update_filter
        self._gh_client: GitHubProvider | None = None
        self._validator = ValidateOperation()
        self._template_dir: str | None = None
        self._org_config: OrganizationConfig | None = None
        self._callback: CallbackFn | None = None
        self._concurrency: int | None = None

    @property
    def template_dir(self) -> str:
        return unwrap(self._template_dir)

    @property
    def org_config(self) -> OrganizationConfig:
        return unwrap(self._org_config)

    @property
    def concurrency(self) -> int | None:
        return self._concurrency

    @concurrency.setter
    def concurrency(self, value: int) -> None:
        self._concurrency = value

    def set_callback(self, fn: CallbackFn) -> None:
        self._callback = fn

    def init(self, config: OtterdogConfig, printer: IndentingPrinter) -> None:
        super().init(config, printer)
        self._validator.init(config, printer)

    async def execute(
        self,
        org_config: OrganizationConfig,
        org_index: int | None = None,
        org_count: int | None = None,
    ) -> int:
        self._org_config = org_config

        self._print_project_header(org_config, org_index, org_count)
        self.printer.level_up()

        try:
            return await self.generate_diff(org_config)
        finally:
            self.printer.level_down()

    async def generate_diff(self, org_config: OrganizationConfig) -> int:
        try:
            self._gh_client = self.setup_github_client(org_config)
        except RuntimeError as e:
            self.printer.print_error(f"invalid credentials\n{e!s}")
            return 1

        try:
            return await self._generate_diff_internal(org_config)
        except RuntimeError as e:
            self.printer.print_error(f"planning aborted: {e!s}")
            return 1
        finally:
            if self._gh_client is not None:
                await self._gh_client.close()

    def setup_github_client(self, org_config: OrganizationConfig) -> GitHubProvider:
        return GitHubProvider(self.get_credentials(org_config, only_token=self.no_web_ui))

    @property
    def gh_client(self) -> GitHubProvider:
        return unwrap(self._gh_client)

    def verbose_output(self):
        return True

    def include_resources_with_secrets(self) -> bool:
        return True

    def resolve_secrets(self) -> bool:
        return True

    async def _generate_diff_internal(self, org_config: OrganizationConfig) -> int:
        github_id = org_config.github_id
        jsonnet_config = org_config.jsonnet_config
        await jsonnet_config.init_template()
        self._template_dir = jsonnet_config.template_dir

        org_file_name = jsonnet_config.org_config_file

        if not await aiofiles.ospath.exists(org_file_name):
            self.printer.print_error(
                f"configuration file '{org_file_name}' does not yet exist, run fetch-config or import first."
            )
            return 1

        try:
            expected_org = self.load_expected_org(github_id, org_file_name)
        except RuntimeError as e:
            self.printer.print_error(f"failed to load configuration\n{e!s}")
            return 1

        # We validate the configuration first and only calculate a plan if
        # there are no validation errors.
        (
            validation_infos,
            validation_warnings,
            validation_errors,
        ) = await self._validator.validate(expected_org, jsonnet_config, self.gh_client)
        if validation_errors > 0:
            self.printer.println("Planning aborted due to validation errors.")
            return validation_errors

        if validation_infos > 0 and not self.printer.is_info_enabled():
            self.printer.println(
                f"there have been {validation_infos} validation infos, enable verbose output to display them."
            )

        try:
            current_org = await self.load_current_org(org_config.name, github_id, jsonnet_config)
        except RuntimeError as e:
            self.printer.print_error(f"failed to load current configuration\n{e!s}")
            return 1

        expected_org, current_org = self.preprocess_orgs(expected_org, current_org)

        diff_status = DiffStatus()
        live_patches = []

        def handle(patch: LivePatch) -> None:
            if not self.include_resources_with_secrets() and patch.requires_secrets():
                return

            live_patches.append(patch)

            match patch.patch_type:
                case LivePatchType.ADD:
                    self.handle_add_object(github_id, unwrap(patch.expected_object), patch.parent_object)
                    diff_status.additions += 1

                case LivePatchType.REMOVE:
                    self.handle_delete_object(github_id, unwrap(patch.current_object), patch.parent_object)
                    diff_status.deletions += 1

                case LivePatchType.CHANGE:
                    diff_status.differences += self.handle_modified_object(
                        github_id,
                        unwrap(patch.changes),
                        patch.forced_update,
                        unwrap(patch.current_object),
                        unwrap(patch.expected_object),
                        patch.parent_object,
                    )

        context = LivePatchContext(
            github_id,
            self.repo_filter,
            self.update_webhooks,
            self.update_secrets,
            self.update_filter,
            current_org.settings if self.coerce_current_org() else None,
            expected_org.settings,
        )
        expected_org.generate_live_patch(current_org, context, handle)

        # resolve secrets for collected patches
        if self.resolve_secrets():
            for live_patch in live_patches:
                if live_patch.expected_object is not None:
                    live_patch.expected_object.resolve_secrets(self.credential_resolver.get_secret)

        status = await self.handle_finish(github_id, diff_status, live_patches)

        if self._callback is not None:
            self._callback(github_id, diff_status, live_patches)

        return status

    def load_expected_org(self, github_id: str, org_file_name: str) -> GitHubOrganization:
        return GitHubOrganization.load_from_file(github_id, org_file_name)

    def coerce_current_org(self) -> bool:
        return False

    async def load_current_org(
        self, project_name: str, github_id: str, jsonnet_config: JsonnetConfig
    ) -> GitHubOrganization:
        return await GitHubOrganization.load_from_provider(
            project_name,
            github_id,
            jsonnet_config,
            self.gh_client,
            self.no_web_ui,
            self.concurrency,
            self.repo_filter,
            exclude_teams=self.config.exclude_teams_pattern,
        )

    def preprocess_orgs(
        self, expected_org: GitHubOrganization, current_org: GitHubOrganization
    ) -> tuple[GitHubOrganization, GitHubOrganization]:
        return expected_org, current_org

    @abstractmethod
    def handle_add_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: ModelObject | None = None,
    ) -> None: ...

    @abstractmethod
    def handle_delete_object(
        self,
        org_id: str,
        model_object: ModelObject,
        parent_object: ModelObject | None = None,
    ) -> None: ...

    @abstractmethod
    def handle_modified_object(
        self,
        org_id: str,
        modified_object: dict[str, Change[Any]],
        forced_update: bool,
        current_object: ModelObject,
        expected_object: ModelObject,
        parent_object: ModelObject | None = None,
    ) -> int: ...

    @abstractmethod
    async def handle_finish(self, org_id: str, diff_status: DiffStatus, patches: list[LivePatch]) -> int: ...
