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
from otterdog.webapp.db.models import BlueprintId, BlueprintModel
from otterdog.webapp.tasks.blueprints.recheck import RecheckBlueprintsTask

CONFIG_REPO = ".eclipsefdn"


def _model(blueprint_id: str, name_pattern: str) -> BlueprintModel:
    blueprint = read_blueprint(
        f"https://example.org/{blueprint_id}.yml",
        {
            "id": blueprint_id,
            "type": "required_file",
            "config": {
                "repo_selector": {"name_pattern": name_pattern},
                "files": [{"path": "SECURITY.md", "content": "x"}],
            },
        },
    )
    return BlueprintModel(
        id=BlueprintId(org_id="osgi", blueprint_type="required_file", blueprint_id=blueprint_id),
        path=blueprint.path,
        config=blueprint.config,
    )


def _organization(*repo_names: str) -> SimpleNamespace:
    repos = [SimpleNamespace(name=name, archived=False) for name in repo_names]
    return SimpleNamespace(
        repositories=repos,
        get_repository=lambda name: next((repo for repo in repos if repo.name == name), None),
    )


async def _run(repo_name: str, blueprint_id: str | None, permission: str = "write"):
    task = RecheckBlueprintsTask(1, "osgi", repo_name, 7, "alice", blueprint_id)

    rest_api = MagicMock()
    rest_api.repo.get_collaborator_permission = AsyncMock(return_value=permission)
    rest_api.issue.create_comment = AsyncMock()

    models = [_model("codeql", "org\\.osgi\\..*"), _model("security-md", r"\.github")]
    config_model = SimpleNamespace(config={})
    organization = _organization("org.osgi.annotation", "org.osgi.framework", ".github")

    with (
        patch("otterdog.webapp.tasks.get_rest_api_for_installation", AsyncMock(return_value=rest_api)),
        patch("otterdog.webapp.db.service.get_blueprints", AsyncMock(return_value=models)),
        patch(
            "otterdog.webapp.tasks.blueprints.recheck.get_installation",
            AsyncMock(return_value=SimpleNamespace(config_repo=CONFIG_REPO)),
        ),
        patch(
            "otterdog.webapp.tasks.blueprints.recheck.get_configuration_by_github_id",
            AsyncMock(return_value=config_model),
        ),
        patch("otterdog.webapp.blueprints.GitHubOrganization.from_model_data", return_value=organization),
        patch("otterdog.webapp.tasks.blueprints.recheck.render_template", AsyncMock(return_value="reply")),
        patch("otterdog.webapp.tasks.blueprints.recheck.get_base_url", return_value="https://otterdog"),
        patch("otterdog.webapp.blueprints.required_file.RequiredFileBlueprint.evaluate", AsyncMock()) as evaluate,
        patch(
            "otterdog.webapp.blueprints.required_file.RequiredFileBlueprint.evaluate_repo", AsyncMock()
        ) as evaluate_repo,
    ):
        result = await task._execute()

    rest_api.issue.create_comment.assert_awaited_once_with("osgi", repo_name, "7", "reply")
    return result, evaluate, evaluate_repo


async def test_config_repo_rechecks_all_matching_repositories_of_every_blueprint():
    result, evaluate, evaluate_repo = await _run(CONFIG_REPO, None)

    assert result.scheduled == {
        "codeql": ["org.osgi.annotation", "org.osgi.framework"],
        "security-md": [".github"],
    }
    assert evaluate.await_count == 2
    # the recheck flag bypasses the per-repository status gate
    assert all(call.kwargs == {"recheck": True} for call in evaluate.await_args_list)
    evaluate_repo.assert_not_awaited()


async def test_config_repo_with_blueprint_id_rechecks_only_that_blueprint():
    result, evaluate, _ = await _run(CONFIG_REPO, "codeql")

    assert list(result.scheduled) == ["codeql"]
    evaluate.assert_awaited_once()


async def test_target_repo_rechecks_only_itself():
    result, evaluate, evaluate_repo = await _run("org.osgi.annotation", None)

    assert result.scheduled == {"codeql": ["org.osgi.annotation"]}
    assert result.not_matching == ["security-md"]
    evaluate.assert_not_awaited()
    evaluate_repo.assert_awaited_once()
    assert evaluate_repo.await_args.args[:3] == (1, "osgi", "org.osgi.annotation")


async def test_unknown_blueprint_id_lists_known_ids():
    result, evaluate, evaluate_repo = await _run(CONFIG_REPO, "does-not-exist")

    assert result.unknown_blueprint_id == "does-not-exist"
    assert result.known_blueprint_ids == ["codeql", "security-md"]
    evaluate.assert_not_awaited()
    evaluate_repo.assert_not_awaited()


async def test_read_access_is_rejected():
    result, evaluate, evaluate_repo = await _run("org.osgi.annotation", None, permission="read")

    assert result.permission_denied is True
    evaluate.assert_not_awaited()
    evaluate_repo.assert_not_awaited()
