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
from otterdog.operations.delete_file import DeleteFileOperation
from otterdog.providers.github.exception import GitHubException
from otterdog.providers.github.rest.content_client import ContentClient
from otterdog.utils import IndentingPrinter

_FILE = {"type": "file", "path": "path/to/file.txt", "sha": "abc123"}
_NOT_FOUND = GitHubException(None, 404, '{"message": "Not Found"}')


class _Provider:
    def __init__(self, rest_api):
        self.rest_api = rest_api

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


def _org_config(github_id: str):
    async def init_template():
        return None

    return pretend.stub(
        name=github_id,
        github_id=github_id,
        jsonnet_config=pretend.stub(init_template=init_template, org_config_file=f"orgs/{github_id}.jsonnet"),
    )


@pytest.fixture
def github(monkeypatch):
    """
    Simulates the configured repositories of each organization, and the responses of GitHub to the requests,
    keyed by organization, then by method. A response that is an exception is raised.
    """
    repositories: dict[str, list] = {}
    responses: dict[str, dict[str, object]] = {}
    sent: list[tuple[str, str]] = []

    async def request_json(method, url_path, data=None, params=None):
        sent.append((method, url_path))
        org_id = url_path.split("/")[2]
        response = responses[org_id][method]
        if isinstance(response, Exception):
            raise response
        return response

    content = ContentClient(pretend.stub(requester=pretend.stub(request_json=request_json)))
    provider = _Provider(pretend.stub(content=content))

    monkeypatch.setattr("otterdog.operations.delete_file.GitHubProvider", lambda credentials: provider)
    monkeypatch.setattr(
        "otterdog.operations.delete_file.GitHubOrganization",
        pretend.stub(load_from_file=lambda github_id, file_name: pretend.stub(repositories=repositories[github_id])),
    )

    return pretend.stub(repositories=repositories, responses=responses, sent=sent)


def _operation() -> DeleteFileOperation:
    operation = DeleteFileOperation(repo="test-repo", path="path/to/file.txt", message=None)

    async def config_file_exists(file_name):
        return True

    operation.check_config_file_exists = config_file_exists
    operation.get_credentials = pretend.call_recorder(lambda org_config, only_token=False: "test-token")
    return operation


async def _execute(operation: DeleteFileOperation, github_id: str = "test-org") -> tuple[int, str]:
    output = StringIO()
    operation.init(None, IndentingPrinter(output))  # type: ignore[arg-type]
    exit_code = await operation.execute(_org_config(github_id))
    return exit_code, output.getvalue()


def _repo(name: str = "test-repo", archived: bool = False):
    return pretend.stub(name=name, archived=archived)


async def test_deletes_the_file(github):
    github.repositories["test-org"] = [_repo()]
    github.responses["test-org"] = {"GET": _FILE, "DELETE": {"commit": {"sha": "def456"}}}

    exit_code, output = await _execute(_operation())

    assert exit_code == 0
    assert "succeeded" in output
    assert [method for method, _ in github.sent] == ["GET", "DELETE"]


async def test_absent_file_is_reported_as_such(github):
    github.repositories["test-org"] = [_repo()]
    github.responses["test-org"] = {"GET": _NOT_FOUND}

    exit_code, output = await _execute(_operation())

    assert exit_code == 0
    assert "not found, nothing to delete" in output
    assert "succeeded" not in output
    assert [method for method, _ in github.sent] == ["GET"]


@pytest.mark.parametrize(
    "responses,expected_message",
    [
        ({"GET": GitHubException(None, 500, "Server Error")}, "failed retrieving content 'path/to/file.txt'"),
        (
            {"GET": _FILE, "DELETE": GitHubException(None, 409, "sha does not match")},
            "failed deleting content 'path/to/file.txt'",
        ),
    ],
)
async def test_failure_is_reported_with_a_non_zero_exit_code(github, responses, expected_message):
    github.repositories["test-org"] = [_repo()]
    github.responses["test-org"] = responses

    exit_code, output = await _execute(_operation())

    assert exit_code == 1
    assert "failed" in output
    assert "Error:" in output
    assert expected_message in output
    assert "succeeded" not in output


@pytest.mark.parametrize(
    "repositories,expected_message",
    [
        ([_repo("other-repo")], "repository 'test-repo' not found in the configuration, skipped"),
        ([_repo(archived=True)], "repository 'test-org/test-repo' is archived, skipped"),
    ],
)
async def test_repository_that_cannot_be_changed_is_skipped_with_a_warning(github, repositories, expected_message):
    github.repositories["test-org"] = repositories
    operation = _operation()

    exit_code, output = await _execute(operation)

    assert exit_code == 0
    assert "Warning:" in output
    assert expected_message in output
    assert github.sent == []
    assert operation.get_credentials.calls == []


def test_organizations_without_the_repository_do_not_fail_the_command(github, monkeypatch, capsys):
    github.repositories.update({"org-a": [_repo("other-repo")], "org-b": [_repo(archived=True)], "org-c": [_repo()]})
    github.responses["org-c"] = {"GET": _FILE, "DELETE": {"commit": {"sha": "def456"}}}

    config = pretend.stub(organization_names=["org-a", "org-b", "org-c"], get_organization_config=_org_config)
    monkeypatch.setattr(cli, "_CONFIG", config)
    monkeypatch.setattr(cli, "set_github_cache", lambda cache: None)
    monkeypatch.setattr(cli, "_STATS", cli._StatsOptions(False, None, "delete-file"))

    with pytest.raises(SystemExit) as exit_info:
        cli._execute_operation([], _operation())

    assert exit_info.value.code == 0
    assert github.sent == [
        ("GET", "/repos/org-c/test-repo/contents/path/to/file.txt"),
        ("DELETE", "/repos/org-c/test-repo/contents/path/to/file.txt"),
    ]
    output = capsys.readouterr().out
    assert "repository 'test-repo' not found in the configuration, skipped" in output
    assert "repository 'org-b/test-repo' is archived, skipped" in output
    assert "succeeded" in output


def test_failure_in_one_organization_does_not_stop_the_others(github, monkeypatch, capsys):
    github.repositories.update({"org-a": [_repo()], "org-b": [_repo()]})
    github.responses["org-a"] = {"GET": _FILE, "DELETE": GitHubException(None, 409, "sha does not match")}
    github.responses["org-b"] = {"GET": _FILE, "DELETE": {"commit": {"sha": "def456"}}}

    config = pretend.stub(organization_names=["org-a", "org-b"], get_organization_config=_org_config)
    monkeypatch.setattr(cli, "_CONFIG", config)
    monkeypatch.setattr(cli, "set_github_cache", lambda cache: None)
    monkeypatch.setattr(cli, "_STATS", cli._StatsOptions(False, None, "delete-file"))

    with pytest.raises(SystemExit) as exit_info:
        cli._execute_operation([], _operation())

    assert exit_info.value.code == 1
    assert ("DELETE", "/repos/org-b/test-repo/contents/path/to/file.txt") in github.sent
    output = capsys.readouterr().out
    assert "failed deleting content" in output
    assert "succeeded" in output


def test_path_is_required(monkeypatch):
    executed = []
    monkeypatch.setattr(cli, "_execute_operation", lambda organizations, operation: executed.append(operation))
    monkeypatch.setattr(cli, "init_logging", lambda *args, **kwargs: None)

    result = CliRunner().invoke(cli.cli, ["delete-file", "--repo", "test-repo"])

    assert result.exit_code == 2
    assert "Missing option '--path'" in result.output
    assert executed == []
