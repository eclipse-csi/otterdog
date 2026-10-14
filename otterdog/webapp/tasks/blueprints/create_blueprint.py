#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from dataclasses import dataclass, field

from quart import render_template

from otterdog.webapp.blueprints.scaffold import (
    UnknownBlueprintTypeError,
    blueprint_file_path,
    default_blueprint_id,
    exact_name_pattern,
    is_valid_blueprint_id,
    render_blueprint_yaml,
    scaffold_blueprint,
    valid_blueprint_types,
)
from otterdog.webapp.db.models import TaskModel
from otterdog.webapp.db.service import get_installation
from otterdog.webapp.tasks import InstallationBasedTask, Task

SCAFFOLD_BRANCH_PREFIX = "otterdog/blueprint-scaffold/"


@dataclass
class CreateBlueprintResult:
    blueprint_id: str | None = None
    file_path: str | None = None
    pull_request_url: str | None = None
    name_pattern: str | list[str] | None = None
    files: list[str] = field(default_factory=list)
    permission_denied: bool = False
    unknown_type: str | None = None
    valid_types: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    already_exists: bool = False
    validation_error: str | None = None
    branch_name: str | None = None
    pull_request_error: str | None = None
    invalid_id: str | None = None


@dataclass(repr=False)
class CreateBlueprintTask(InstallationBasedTask, Task[CreateBlueprintResult]):
    """
    `/otterdog create blueprint <type> [--id <id>] [--from <path>]... [--filter <regex>]`:
    scaffolds `otterdog/blueprints/<id>.yml` and opens a pull request against the configuration
    repository. Files named with `--from` are taken from the repository the comment is made in,
    so an existing repository serves as the reference for its siblings.
    """

    installation_id: int
    org_id: str
    repo_name: str
    issue_number: int
    author: str
    blueprint_type: str
    blueprint_id: str | None = None
    from_paths: list[str] = field(default_factory=list)
    name_pattern: str | None = None

    def create_task_model(self):
        return TaskModel(
            type=type(self).__name__,
            org_id=self.org_id,
            repo_name=self.repo_name,
            pull_request=self.issue_number,
        )

    async def _execute(self) -> CreateBlueprintResult:
        self.logger.info(
            "creating blueprint of type '%s' requested by '%s' in '%s/%s#%d'",
            self.blueprint_type,
            self.author,
            self.org_id,
            self.repo_name,
            self.issue_number,
        )

        result = CreateBlueprintResult(valid_types=valid_blueprint_types())
        rest_api = await self.rest_api

        if not await self.has_write_access(self.org_id, self.repo_name, self.author):
            result.permission_denied = True
            return await self._finish(result)

        if self.blueprint_type not in result.valid_types:
            result.unknown_type = self.blueprint_type
            return await self._finish(result)

        installation = await get_installation(self.installation_id)
        if installation is None or installation.config_repo is None:
            raise RuntimeError(f"no installation with a config repo found for org '{self.org_id}'")

        config_repo = installation.config_repo
        is_config_repo = config_repo == self.repo_name

        files = await self._fetch_files(result)
        if len(result.missing_files) > 0:
            return await self._finish(result)

        blueprint_id = self.blueprint_id or default_blueprint_id(self.blueprint_type, files)
        if not is_valid_blueprint_id(blueprint_id):
            result.invalid_id = blueprint_id
            return await self._finish(result)

        result.blueprint_id = blueprint_id
        result.name_pattern = self._resolve_name_pattern(is_config_repo)
        result.files = list(files)
        result.file_path = blueprint_file_path(blueprint_id)

        data = self._scaffold(result, files, is_config_repo)
        if data is None:
            return await self._finish(result)

        default_branch = await rest_api.repo.get_default_branch(self.org_id, config_repo)
        if await self._blueprint_exists(config_repo, result.file_path, default_branch):
            result.already_exists = True
            return await self._finish(result)

        await self._push_and_open_pull_request(config_repo, default_branch, result, data)
        return await self._finish(result)

    async def _fetch_files(self, result: CreateBlueprintResult) -> dict[str, str]:
        """Files are taken from the repository the comment is made in."""
        rest_api = await self.rest_api
        files: dict[str, str] = {}
        for path in self.from_paths:
            try:
                files[path] = await rest_api.content.get_content(self.org_id, self.repo_name, path)
            except RuntimeError:
                result.missing_files.append(path)
        return files

    def _resolve_name_pattern(self, is_config_repo: bool) -> str | None:
        if self.blueprint_type == "append_configuration":
            # this type targets the configuration repository and has no repository selector
            return None
        if self.name_pattern is not None:
            return self.name_pattern
        if not is_config_repo:
            # start narrow: the blueprint only applies to the reference repository
            return exact_name_pattern(self.repo_name)
        return None

    def _scaffold(self, result: CreateBlueprintResult, files: dict[str, str], is_config_repo: bool) -> dict | None:
        origin = (
            f"{self.org_id}/{self.repo_name}#{self.issue_number}" if not is_config_repo else f"#{self.issue_number}"
        )
        try:
            return scaffold_blueprint(
                self.blueprint_type,
                result.blueprint_id or "",
                result.name_pattern,
                files,
                description=f"Scaffolded by @{self.author} from {origin}.",
            )
        except UnknownBlueprintTypeError:
            result.unknown_type = self.blueprint_type
        except ValueError as ex:
            result.validation_error = str(ex)
        return None

    async def _blueprint_exists(self, config_repo: str, file_path: str, default_branch: str) -> bool:
        rest_api = await self.rest_api
        try:
            await rest_api.content.get_content(self.org_id, config_repo, file_path, default_branch)
            return True
        except RuntimeError:
            return False

    async def _push_and_open_pull_request(
        self, config_repo: str, default_branch: str, result: CreateBlueprintResult, data: dict
    ) -> None:
        rest_api = await self.rest_api
        blueprint_id = result.blueprint_id
        branch_name = f"{SCAFFOLD_BRANCH_PREFIX}{blueprint_id}"
        title = f"feat(blueprints): add blueprint `{blueprint_id}`"

        default_branch_data = await rest_api.reference.get_branch_reference(self.org_id, config_repo, default_branch)
        try:
            await rest_api.reference.get_branch_reference(self.org_id, config_repo, branch_name)
        except RuntimeError:
            await rest_api.reference.create_reference(
                self.org_id, config_repo, branch_name, default_branch_data["object"]["sha"]
            )

        await rest_api.content.update_content(
            self.org_id, config_repo, result.file_path or "", render_blueprint_yaml(data), branch_name, title
        )

        pr_body = await render_template(
            "comment/blueprint_scaffold_pr_body.txt",
            result=result,
            author=self.author,
            org_id=self.org_id,
            repo_name=self.repo_name,
            issue_number=self.issue_number,
            blueprint_type=self.blueprint_type,
        )

        try:
            created_pr = await rest_api.pull_request.create_pull_request(
                self.org_id, config_repo, title, branch_name, default_branch, pr_body
            )
            result.pull_request_url = created_pr.get("html_url")
        except RuntimeError as ex:
            # typically a pull request for the scaffold branch exists already
            self.logger.warning(f"failed to open a pull request for branch '{branch_name}'", exc_info=ex)
            result.pull_request_url = None
            result.branch_name = branch_name
            result.pull_request_error = str(ex).splitlines()[0]

    async def _post_execute(self, result_or_exception: CreateBlueprintResult | Exception) -> None:
        if isinstance(result_or_exception, Exception):
            await self.comment_on_failure(
                self.org_id,
                self.repo_name,
                self.issue_number,
                self.author,
                f"create blueprint {self.blueprint_type}",
                result_or_exception,
            )

    async def _finish(self, result: CreateBlueprintResult) -> CreateBlueprintResult:
        comment = await render_template(
            "comment/create_blueprint_comment.txt",
            result=result,
            author=self.author,
            blueprint_type=self.blueprint_type,
        )

        rest_api = await self.rest_api
        await rest_api.issue.create_comment(self.org_id, self.repo_name, str(self.issue_number), comment)
        return result

    def __repr__(self) -> str:
        return (
            f"CreateBlueprintTask(repo='{self.org_id}/{self.repo_name}', issue={self.issue_number}, "
            f"type='{self.blueprint_type}', id='{self.blueprint_id}')"
        )
