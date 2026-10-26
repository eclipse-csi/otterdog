#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json

import pretend
import pytest

from otterdog import cli
from otterdog.operations import Operation
from otterdog.providers.github.stats import RequestOutcome, RequestRecorder, RequestStatistics


class _RequestingOperation(Operation):
    """Pretends to send a number of requests per organization, optionally failing for one."""

    def __init__(
        self,
        requests: dict[str, int],
        failure: BaseException | None = None,
        failing_org: str = "",
        exit_code: int = 0,
    ) -> None:
        super().__init__()
        self._requests = requests
        self._failure = failure
        self._failing_org = failing_org
        self._exit_code = exit_code

    def pre_execute(self) -> None:
        pass

    async def execute(self, org_config, org_index=None, org_count=None) -> int:
        recorder = RequestRecorder("rest", RequestStatistics(), charge_responses=True)
        for _ in range(self._requests[org_config.github_id]):
            recorder.record(RequestOutcome("GET /orgs/{org}", quota_resource="core"))

        if self._failure is not None and org_config.github_id == self._failing_org:
            raise self._failure

        return self._exit_code if org_config.github_id == self._failing_org else 0


@pytest.fixture
def run_operation(monkeypatch):
    config = pretend.stub(
        organization_names=["org-a", "org-b"],
        get_organization_config=lambda name: pretend.stub(name=name, github_id=name),
    )
    monkeypatch.setattr(cli, "_CONFIG", config)
    monkeypatch.setattr(cli, "set_github_cache", lambda cache: None)

    def run(operation: Operation, show: bool = False, file: str | None = None) -> int:
        monkeypatch.setattr(cli, "_STATS", cli._StatsOptions(show, file, "plan"))

        with pytest.raises(SystemExit) as exit_info:
            cli._execute_operation([], operation)

        return exit_info.value.code

    return run


def test_statistics_file_per_organization(run_operation, tmp_path):
    stats_file = tmp_path / "stats.json"

    exit_code = run_operation(_RequestingOperation({"org-a": 3, "org-b": 2}), file=str(stats_file))

    data = json.loads(stats_file.read_text())
    assert exit_code == 0
    assert data["command"] == "plan"
    assert data["outcome"] == "completed"
    assert data["total"]["requests"] == 5
    assert data["apis"]["rest"]["quota_cost"] == {"core": 5}
    assert data["organizations"]["org-a"]["rest"]["requests"] == 3
    assert data["organizations"]["org-b"]["rest"]["requests"] == 2


def test_statistics_are_printed_to_stderr_only_when_requested(run_operation, capsys):
    run_operation(_RequestingOperation({"org-a": 1, "org-b": 1}))
    assert "GitHub API usage" not in capsys.readouterr().err

    run_operation(_RequestingOperation({"org-a": 1, "org-b": 1}), show=True)
    captured = capsys.readouterr()
    assert "GitHub API usage · plan · 2 organizations" in captured.err
    assert "GitHub API usage" not in captured.out


def test_statistics_survive_a_failure(run_operation, tmp_path, capsys):
    stats_file = tmp_path / "stats.json"
    operation = _RequestingOperation({"org-a": 3, "org-b": 2}, RuntimeError("boom"), "org-b")

    exit_code = run_operation(operation, show=True, file=str(stats_file))

    data = json.loads(stats_file.read_text())
    assert exit_code == 2
    assert data["outcome"] == "failed"
    assert data["total"]["requests"] == 5
    assert "failed" in capsys.readouterr().err


def test_failure_reported_by_exit_code(run_operation, tmp_path):
    stats_file = tmp_path / "stats.json"
    # e.g. a validation reports its number of errors
    operation = _RequestingOperation({"org-a": 3, "org-b": 2}, failing_org="org-a", exit_code=4)

    exit_code = run_operation(operation, file=str(stats_file))

    data = json.loads(stats_file.read_text())
    assert exit_code == 4
    assert data["outcome"] == "failed"
    assert data["total"]["requests"] == 5


def test_statistics_survive_an_interruption(run_operation, tmp_path):
    stats_file = tmp_path / "stats.json"
    operation = _RequestingOperation({"org-a": 3, "org-b": 2}, KeyboardInterrupt(), "org-a")

    exit_code = run_operation(operation, file=str(stats_file))

    data = json.loads(stats_file.read_text())
    assert exit_code == 130
    assert data["outcome"] == "interrupted"
    assert data["total"]["requests"] == 3
    assert list(data["organizations"]) == ["org-a"]


def test_unwritable_statistics_file_does_not_change_exit_code(run_operation, tmp_path, capsys):
    exit_code = run_operation(_RequestingOperation({"org-a": 1, "org-b": 1}), file=str(tmp_path / "missing" / "x"))

    assert exit_code == 0
    assert "failed to write github api usage statistics" in capsys.readouterr().err


def test_stats_options_are_available_on_organization_commands():
    from click.testing import CliRunner

    result = CliRunner().invoke(cli.cli, ["plan", "--help"])

    assert result.exit_code == 0
    assert "--stats " in result.output
    assert "OTTERDOG_STATS" in result.output
    assert "--stats-file" in result.output
