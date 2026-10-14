#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from otterdog.webapp.blueprints import read_blueprint
from otterdog.webapp.tasks.blueprints.check_scorecard_integration import CheckScorecardIntegrationTask

INLINE_WORKFLOW = """
name: Scorecard
on: [push]
jobs:
  analysis:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ossf/scorecard-action@v2.4.0
"""

STUB_WORKFLOW = """
name: Scorecard
on: [push]
jobs:
  analysis:
    uses: osgi/workflows/.github/workflows/scorecard.yml@main
"""

UNRELATED_WORKFLOW = """
name: Build
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""


def _blueprint(**config):
    return read_blueprint(
        "https://example.org/blueprint.yml",
        {"id": "scorecard", "type": "scorecard_integration", "config": {"workflow_content": "name: x", **config}},
    )


def _task(blueprint, repo_workflows: dict[str, str], remote_workflows: dict[tuple, str] | None = None):
    task = CheckScorecardIntegrationTask(1, "osgi", "org.osgi.maven.pom", blueprint, SimpleNamespace(config={}))

    rest_api = MagicMock()
    rest_api.action.get_workflows = AsyncMock(
        return_value=[{"path": path} for path in repo_workflows] + [{"path": "dynamic/pages/pages-build-deployment"}]
    )

    async def get_content(owner, repo, path, ref=None):
        if (owner, repo) == ("osgi", "org.osgi.maven.pom"):
            return repo_workflows[path]
        if remote_workflows is not None and (owner, repo, path, ref) in remote_workflows:
            return remote_workflows[(owner, repo, path, ref)]
        raise RuntimeError("not found")

    rest_api.content.get_content = AsyncMock(side_effect=get_content)
    rest_api.repo.get_default_branch = AsyncMock(return_value="main")
    return task, rest_api


async def _find(task, rest_api) -> bool:
    with patch("otterdog.webapp.tasks.get_rest_api_for_installation", AsyncMock(return_value=rest_api)):
        return await task._find_scorecard_integration()


async def test_inline_scorecard_action_is_found():
    task, rest_api = _task(_blueprint(), {".github/workflows/scorecard.yml": INLINE_WORKFLOW})
    assert await _find(task, rest_api) is True


async def test_unrelated_workflow_is_not_a_scorecard_integration():
    task, rest_api = _task(_blueprint(), {".github/workflows/build.yml": UNRELATED_WORKFLOW})
    assert await _find(task, rest_api) is False


async def test_reusable_workflow_running_scorecard_is_found():
    # regression: a stub calling a central reusable workflow was overwritten by the inline workflow
    task, rest_api = _task(
        _blueprint(),
        {".github/workflows/scorecard.yml": STUB_WORKFLOW},
        {("osgi", "workflows", ".github/workflows/scorecard.yml", "main"): INLINE_WORKFLOW},
    )
    assert await _find(task, rest_api) is True


async def test_reusable_workflow_without_scorecard_is_not_found():
    task, rest_api = _task(
        _blueprint(),
        {".github/workflows/scorecard.yml": STUB_WORKFLOW},
        {("osgi", "workflows", ".github/workflows/scorecard.yml", "main"): UNRELATED_WORKFLOW},
    )
    assert await _find(task, rest_api) is False


async def test_unreachable_reusable_workflow_is_not_found():
    task, rest_api = _task(_blueprint(), {".github/workflows/scorecard.yml": STUB_WORKFLOW})
    assert await _find(task, rest_api) is False


@pytest.mark.parametrize(
    "pattern, expected",
    [
        (r"osgi/workflows/\.github/workflows/scorecard\.yml@.*", True),
        (r"osgi/workflows/.*", True),
        (r"other-org/workflows/.*", False),
    ],
)
async def test_allow_listed_reusable_workflow_is_accepted_without_fetching(pattern, expected):
    task, rest_api = _task(
        _blueprint(scorecard_workflow_refs=[pattern]),
        {".github/workflows/scorecard.yml": STUB_WORKFLOW},
    )
    assert await _find(task, rest_api) is expected
    if expected:
        # the remote workflow was never fetched
        assert all(
            call.args[:2] == ("osgi", "org.osgi.maven.pom") for call in rest_api.content.get_content.await_args_list
        )
