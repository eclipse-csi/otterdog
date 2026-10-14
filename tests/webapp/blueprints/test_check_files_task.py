#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from otterdog.webapp.blueprints import read_blueprint
from otterdog.webapp.blueprints.required_file import RequiredFile
from otterdog.webapp.tasks.blueprints import CheckResult
from otterdog.webapp.tasks.blueprints.check_files import CheckFilesTask


def _blueprint():
    return read_blueprint(
        "https://example.org/files.yml",
        {
            "id": "files",
            "type": "required_file",
            "config": {
                "labels": ["security"],
                "files": [
                    {"path": "SECURITY.md", "content": "policy", "strict": False},
                    {"path": ".github/workflows/codeql.yml", "content": "workflow", "strict": True},
                ],
            },
        },
    )


async def _process(
    branch_is_fresh: bool,
    existing_pr: int | None,
    existing_body: str = "",
    existing_labels: tuple[str, ...] = (),
):
    blueprint = _blueprint()
    task = CheckFilesTask(1, "osgi", "org.osgi.annotation", blueprint, SimpleNamespace(config={}))
    result = CheckResult(remediation_needed=False)

    rest_api = MagicMock()
    rest_api.repo.get_default_branch = AsyncMock(return_value="main")
    rest_api.content.update_content = AsyncMock(return_value=True)
    rest_api.pull_request.create_pull_request = AsyncMock(return_value={"number": 9})
    rest_api.pull_request.update_pull_request = AsyncMock()
    rest_api.pull_request.get_pull_request = AsyncMock(
        return_value={"body": existing_body, "labels": [{"name": label} for label in existing_labels]}
    )
    rest_api.pull_request.request_reviews = AsyncMock()
    rest_api.issue.add_labels = AsyncMock()
    rest_api.issue.add_assignees = AsyncMock()

    files = [(RequiredFile(**f.model_dump()), f.content) for f in blueprint.files]

    with (
        patch("otterdog.webapp.tasks.get_rest_api_for_installation", AsyncMock(return_value=rest_api)),
        patch.object(CheckFilesTask, "_prepare_branch", AsyncMock(return_value=branch_is_fresh)),
        patch.object(CheckFilesTask, "_find_existing_pull_request", AsyncMock(return_value=existing_pr)),
        patch("otterdog.webapp.tasks.blueprints.render_template", AsyncMock(return_value="body")),
        patch("otterdog.webapp.tasks.blueprints.get_base_url", return_value="https://otterdog"),
    ):
        await task._process_files(files, result)

    return result, rest_api


def _written_paths(rest_api) -> list[str]:
    return [call.args[2] for call in rest_api.content.update_content.await_args_list]


async def test_fresh_branch_writes_every_file_and_records_revision():
    result, rest_api = await _process(branch_is_fresh=True, existing_pr=None)

    assert _written_paths(rest_api) == ["SECURITY.md", ".github/workflows/codeql.yml"]
    assert result.content_written is True
    assert result.remediation_pr == 9
    rest_api.issue.add_labels.assert_awaited_once_with(
        "osgi", "org.osgi.annotation", 9, ["otterdog", "blueprint:files", "security"]
    )


async def test_branch_with_maintainer_commits_keeps_non_strict_files():
    result, rest_api = await _process(branch_is_fresh=False, existing_pr=None)

    assert _written_paths(rest_api) == [".github/workflows/codeql.yml"]
    # not every file carries the current content, so no revision is recorded
    assert result.content_written is False


async def test_existing_pull_request_is_refreshed_instead_of_recreated():
    result, rest_api = await _process(branch_is_fresh=True, existing_pr=4)

    assert result.remediation_pr == 4
    rest_api.pull_request.create_pull_request.assert_not_awaited()
    rest_api.pull_request.update_pull_request.assert_awaited_once_with("osgi", "org.osgi.annotation", 4, body="body")
    rest_api.issue.add_labels.assert_awaited_once()


async def test_existing_pull_request_is_not_touched_when_body_and_labels_are_current():
    result, rest_api = await _process(
        branch_is_fresh=True,
        existing_pr=4,
        existing_body="body",
        existing_labels=("otterdog", "blueprint:files", "security"),
    )

    assert result.remediation_pr == 4
    rest_api.pull_request.update_pull_request.assert_not_awaited()
    rest_api.issue.add_labels.assert_not_awaited()
