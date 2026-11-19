#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from io import StringIO

import pretend
import pytest
from click.testing import CliRunner

from otterdog import cli
from otterdog.operations.dispatch_workflow import DispatchWorkflowOperation
from otterdog.providers.github import GitHubProvider
from otterdog.providers.github.exception import GitHubException
from otterdog.providers.github.rest.repo_client import RepoClient
from otterdog.utils import IndentingPrinter


@pytest.fixture
def github(monkeypatch):
    """
    Simulates the responses of GitHub per organization: the data of the repository, or an exception to raise,
    and the status and body of the dispatch.
    """
    repo_data: dict[str, object] = {}
    dispatches: dict[str, tuple[int, str]] = {}
    sent: list[tuple[str, str]] = []

    async def request_json(method, url_path, data=None, params=None):
        sent.append((method, url_path))
        response = repo_data[url_path.split("/")[2]]
        if isinstance(response, Exception):
            raise response
        return response

    async def request_raw(method, url_path, data=None, params=None):
        sent.append((method, url_path))
        return dispatches[url_path.split("/")[2]]

    requester = pretend.stub(request_json=request_json, request_raw=request_raw)
    rest_api = pretend.stub(repo=RepoClient(pretend.stub(requester=requester)))

    class _Provider:
        def __init__(self, credentials):
            self.rest_api = rest_api

        dispatch_workflow = GitHubProvider.dispatch_workflow

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr("otterdog.operations.dispatch_workflow.GitHubProvider", _Provider)

    return pretend.stub(repo_data=repo_data, dispatches=dispatches, sent=sent)


def _operation() -> DispatchWorkflowOperation:
    operation = DispatchWorkflowOperation(repo_name=".eclipsefdn", workflow_name="ci.yml")
    operation.get_credentials = lambda org_config, only_token=False: "test-token"
    return operation


async def _execute(operation: DispatchWorkflowOperation) -> tuple[int, str]:
    output = StringIO()
    operation.init(None, IndentingPrinter(output))  # type: ignore[arg-type]
    exit_code = await operation.execute(pretend.stub(name="test-org", github_id="test-org"))
    return exit_code, output.getvalue()


async def test_dispatches_the_workflow(github):
    github.repo_data["test-org"] = {"default_branch": "main"}
    github.dispatches["test-org"] = (204, "")

    exit_code, output = await _execute(_operation())

    assert exit_code == 0
    assert "workflow 'ci.yml' dispatched for repo '.eclipsefdn'" in output
    assert ("POST", "/repos/test-org/.eclipsefdn/actions/workflows/ci.yml/dispatches") in github.sent


async def test_failed_dispatch_is_reported_with_the_response(github):
    github.repo_data["test-org"] = {"default_branch": "main"}
    github.dispatches["test-org"] = (422, '{"message": "Workflow does not have workflow_dispatch trigger"}')

    exit_code, output = await _execute(_operation())

    assert exit_code == 1
    assert "Error:" in output
    assert "failed to dispatch workflow 'ci.yml' for repo '.eclipsefdn'" in output
    assert "Workflow does not have workflow_dispatch trigger" in output
    assert "422" in output
    assert "dispatched for repo" not in output


async def test_unknown_repository_is_reported(github):
    github.repo_data["test-org"] = GitHubException(None, 404, '{"message": "Not Found"}')

    exit_code, output = await _execute(_operation())

    assert exit_code == 1
    assert "Error:" in output
    assert "failed retrieving simple repo data for repo 'test-org/.eclipsefdn'" in output
    assert [method for method, _ in github.sent] == ["GET"]


def test_failure_in_one_organization_does_not_stop_the_others(github, monkeypatch, capsys):
    github.repo_data.update({"org-a": {"default_branch": "main"}, "org-b": {"default_branch": "main"}})
    github.dispatches.update({"org-a": (500, "Server Error"), "org-b": (204, "")})

    config = pretend.stub(
        organization_names=["org-a", "org-b"],
        get_organization_config=lambda name: pretend.stub(name=name, github_id=name),
    )
    monkeypatch.setattr(cli, "_CONFIG", config)
    monkeypatch.setattr(cli, "set_github_cache", lambda cache: None)
    monkeypatch.setattr(cli, "_STATS", cli._StatsOptions(False, None, "dispatch-workflow"))

    operation = _operation()
    with pytest.raises(SystemExit) as exit_info:
        cli._execute_operation([], operation)

    assert exit_info.value.code == 1
    assert ("POST", "/repos/org-b/.eclipsefdn/actions/workflows/ci.yml/dispatches") in github.sent
    output = capsys.readouterr().out
    assert "failed to dispatch workflow 'ci.yml'" in output
    assert "workflow 'ci.yml' dispatched for repo '.eclipsefdn'" in output


def test_workflow_is_required(monkeypatch):
    executed = []
    monkeypatch.setattr(cli, "_execute_operation", lambda organizations, operation: executed.append(operation))
    monkeypatch.setattr(cli, "init_logging", lambda *args, **kwargs: None)

    result = CliRunner().invoke(cli.cli, ["dispatch-workflow"])

    assert result.exit_code == 2
    assert "Missing option '--workflow'" in result.output
    assert executed == []
