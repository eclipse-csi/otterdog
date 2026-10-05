#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import yaml

from otterdog.webapp.tasks.blueprints.create_blueprint import CreateBlueprintTask

CONFIG_REPO = ".eclipsefdn"
MODULE = "otterdog.webapp.tasks.blueprints.create_blueprint"


async def _run(
    repo_name: str,
    blueprint_type: str = "required_file",
    blueprint_id=None,
    from_paths=(),
    name_pattern=None,
    existing_blueprint: bool = False,
    permission: str = "write",
    pull_request_fails: bool = False,
):
    task = CreateBlueprintTask(
        1, "osgi", repo_name, 7, "alice", blueprint_type, blueprint_id, list(from_paths), name_pattern
    )

    repo_files = {("osgi", repo_name, ".github/workflows/build.yml"): "name: Build\non: [push]\n"}
    written: dict = {}

    async def get_content(org, repo, path, ref=None):
        if repo == CONFIG_REPO and path.startswith("otterdog/blueprints/"):
            if existing_blueprint:
                return "exists"
            raise RuntimeError("not found")
        if (org, repo, path) in repo_files:
            return repo_files[(org, repo, path)]
        raise RuntimeError("not found")

    async def update_content(org, repo, path, content, ref, message):
        written[(repo, ref, path)] = content
        return True

    rest_api = MagicMock()
    rest_api.repo.get_collaborator_permission = AsyncMock(return_value=permission)
    rest_api.repo.get_default_branch = AsyncMock(return_value="main")
    rest_api.content.get_content = AsyncMock(side_effect=get_content)
    rest_api.content.update_content = AsyncMock(side_effect=update_content)
    rest_api.reference.get_branch_reference = AsyncMock(
        side_effect=lambda org, repo, ref: (
            {"object": {"sha": "abc"}} if ref == "main" else (_ for _ in ()).throw(RuntimeError())
        )
    )
    rest_api.reference.create_reference = AsyncMock()
    rest_api.pull_request.create_pull_request = AsyncMock(
        side_effect=RuntimeError("failed creating pull request:\n422 A pull request already exists")
        if pull_request_fails
        else None,
        return_value={"number": 42, "html_url": "https://github.com/osgi/.eclipsefdn/pull/42"},
    )
    rest_api.issue.create_comment = AsyncMock()

    with (
        patch("otterdog.webapp.tasks.get_rest_api_for_installation", AsyncMock(return_value=rest_api)),
        patch(f"{MODULE}.get_installation", AsyncMock(return_value=SimpleNamespace(config_repo=CONFIG_REPO))),
        patch(f"{MODULE}.render_template", AsyncMock(return_value="reply")),
    ):
        result = await task._execute()

    rest_api.issue.create_comment.assert_awaited_once_with("osgi", repo_name, "7", "reply")
    return result, rest_api, written


async def test_target_repo_scaffolds_from_file_with_exact_selector():
    result, rest_api, written = await _run("org.osgi.annotation", from_paths=[".github/workflows/build.yml"])

    assert result.pull_request_url == "https://github.com/osgi/.eclipsefdn/pull/42"
    assert result.blueprint_id == "require-build"
    assert result.file_path == "otterdog/blueprints/require-build.yml"
    assert result.name_pattern == "^org\\.osgi\\.annotation$"

    content = written[
        (CONFIG_REPO, "otterdog/blueprint-scaffold/require-build", "otterdog/blueprints/require-build.yml")
    ]
    data = yaml.safe_load(content)
    assert data["type"] == "required_file"
    assert data["config"]["repo_selector"]["name_pattern"] == "^org\\.osgi\\.annotation$"
    assert data["config"]["files"][0]["path"] == ".github/workflows/build.yml"
    assert data["config"]["files"][0]["content"] == "name: Build\non: [push]\n"

    rest_api.reference.create_reference.assert_awaited_once_with(
        "osgi", CONFIG_REPO, "otterdog/blueprint-scaffold/require-build", "abc"
    )
    assert rest_api.pull_request.create_pull_request.await_args.args[:5] == (
        "osgi",
        CONFIG_REPO,
        "feat(blueprints): add blueprint `require-build`",
        "otterdog/blueprint-scaffold/require-build",
        "main",
    )


async def test_config_repo_without_filter_has_no_selector():
    result, _, written = await _run(CONFIG_REPO, blueprint_id="pin-all", blueprint_type="pin_workflow")

    assert result.name_pattern is None
    data = yaml.safe_load(next(iter(written.values())))
    assert "repo_selector" not in data["config"]


async def test_explicit_filter_and_id_are_used():
    result, _, written = await _run("org.osgi.annotation", blueprint_id="ci", name_pattern="^org\\.osgi\\..*")

    assert result.blueprint_id == "ci"
    assert result.name_pattern == "^org\\.osgi\\..*"
    assert (CONFIG_REPO, "otterdog/blueprint-scaffold/ci", "otterdog/blueprints/ci.yml") in written


async def test_unknown_type_is_reported():
    result, rest_api, _ = await _run("org.osgi.annotation", blueprint_type="nope")

    assert result.unknown_type == "nope"
    assert "required_file" in result.valid_types
    rest_api.pull_request.create_pull_request.assert_not_awaited()


async def test_missing_file_is_reported():
    result, rest_api, _ = await _run("org.osgi.annotation", from_paths=["does/not/exist.yml"])

    assert result.missing_files == ["does/not/exist.yml"]
    rest_api.pull_request.create_pull_request.assert_not_awaited()


async def test_existing_blueprint_is_not_overwritten():
    result, rest_api, written = await _run("org.osgi.annotation", blueprint_id="ci", existing_blueprint=True)

    assert result.already_exists is True
    assert written == {}
    rest_api.pull_request.create_pull_request.assert_not_awaited()


async def test_read_access_is_rejected():
    result, rest_api, _ = await _run("org.osgi.annotation", permission="read")

    assert result.permission_denied is True
    rest_api.pull_request.create_pull_request.assert_not_awaited()


async def test_failing_pull_request_is_reported_not_raised():
    result, rest_api, written = await _run("org.osgi.annotation", blueprint_id="ci", pull_request_fails=True)

    assert result.pull_request_url is None
    assert result.branch_name == "otterdog/blueprint-scaffold/ci"
    assert result.pull_request_error == "failed creating pull request:"
    assert len(written) == 1
    rest_api.issue.create_comment.assert_awaited_once()


async def test_invalid_id_is_rejected():
    result, rest_api, written = await _run("org.osgi.annotation", blueprint_id="foo/bar")

    assert result.invalid_id == "foo/bar"
    assert written == {}
    rest_api.pull_request.create_pull_request.assert_not_awaited()


async def test_append_configuration_has_no_selector_even_with_filter():
    result, _, written = await _run(
        "org.osgi.annotation", blueprint_type="append_configuration", blueprint_id="append", name_pattern="^x$"
    )

    assert result.name_pattern is None
    data = yaml.safe_load(next(iter(written.values())))
    assert "repo_selector" not in data["config"]


async def test_unexpected_error_is_reported_as_comment():
    task = CreateBlueprintTask(1, "osgi", "org.osgi.annotation", 7, "alice", "required_file")

    rest_api = MagicMock()
    rest_api.repo.get_collaborator_permission = AsyncMock(side_effect=RuntimeError("boom\nmore"))
    rest_api.issue.create_comment = AsyncMock()
    rest_api.close = AsyncMock()

    with (
        patch("otterdog.webapp.tasks.get_rest_api_for_installation", AsyncMock(return_value=rest_api)),
        patch("otterdog.webapp.tasks.render_template", AsyncMock(return_value="failed")),
        patch("otterdog.webapp.tasks.create_task", AsyncMock()),
        patch("otterdog.webapp.tasks.schedule_task", AsyncMock()),
        patch("otterdog.webapp.tasks.fail_task", AsyncMock()),
        patch("otterdog.webapp.tasks.finish_task", AsyncMock()),
    ):
        outcome = await task.execute()

    assert isinstance(outcome, RuntimeError)
    rest_api.issue.create_comment.assert_awaited_once_with("osgi", "org.osgi.annotation", "7", "failed")
