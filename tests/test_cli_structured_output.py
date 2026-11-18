#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
import logging
from dataclasses import dataclass

import pretend
import pytest
from rich.logging import RichHandler

from otterdog import cli
from otterdog.logging import CONSOLE_STDOUT
from otterdog.operations import list_apps
from otterdog.operations.check_status import CheckStatusOperation
from otterdog.operations.list_apps import ListAppsOperation

# longer than the width of a console that is not a terminal
_LONG_SLUG = "app-" + "x" * 120

_logger = logging.getLogger("otterdog.tests")


@dataclass
class _Result:
    exit_code: int
    stdout: str
    stderr: str


@pytest.fixture
def run_cli(monkeypatch, capsys):
    """
    Runs the CLI on the organizations 'org-a' and 'org-b', with the logging handler of init_logging, which the test
    session does not install.

    The output is captured with capsys rather than CliRunner, whose streams the live logging of pytest replaces on
    each log record.
    """
    config = pretend.stub(
        organization_names=["org-a", "org-b"],
        get_organization_config=lambda name: pretend.stub(name=f"project-{name}", github_id=name),
        default_no_web_ui=True,
    )
    monkeypatch.setattr(cli, "load_otterdog_config", lambda config_file, local_mode: config)
    monkeypatch.setattr(cli, "set_github_cache", lambda cache: None)
    # the statistics, which these variables enable, are written to stderr or to a file
    monkeypatch.delenv("OTTERDOG_STATS", raising=False)
    monkeypatch.delenv("OTTERDOG_STATS_FILE", raising=False)

    init_logging = cli.init_logging
    monkeypatch.setattr(cli, "init_logging", lambda verbose: init_logging(verbose, setup_python_logger=False))
    otterdog_logger = logging.getLogger("otterdog")
    otterdog_level = otterdog_logger.level

    # without the columns that wrap the messages of the tests
    handler = RichHandler(console=CONSOLE_STDOUT, show_time=False, show_path=False)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    def run(*args: str) -> _Result:
        capsys.readouterr()
        with pytest.raises(SystemExit) as exit_info:
            cli.cli.main(list(args), prog_name="otterdog", standalone_mode=False)

        captured = capsys.readouterr()
        return _Result(exit_info.value.code, captured.out, captured.err)

    try:
        yield run
    finally:
        root_logger.removeHandler(handler)
        init_logging(0, setup_python_logger=False)
        otterdog_logger.setLevel(otterdog_level)


class _Provider:
    """Lists one app per organization and logs a warning, failing for the organizations given."""

    failing_orgs: tuple[str, ...] = ()

    def __init__(self, credentials):
        self.rest_api = pretend.stub(org=pretend.stub(get_app_installations=self._get_app_installations))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def _get_app_installations(self, github_id: str) -> list[dict]:
        _logger.warning("partial apps of %s", github_id)
        if github_id in self.failing_orgs:
            raise RuntimeError(f"failed retrieving app installations of '{github_id}'")

        return [{"app_id": 1, "app_slug": f"{github_id}-{_LONG_SLUG}", "permissions": {"contents": "read"}}]


def _app(github_id: str) -> dict:
    return {"app_id": 1, "app_slug": f"{github_id}-{_LONG_SLUG}", "permissions": {"contents": "read"}}


@pytest.fixture
def github(monkeypatch):
    def get_credentials(self, org_config, only_token=False):
        if org_config.github_id == "org-a":
            raise RuntimeError("no token for 'org-a'")
        return pretend.stub()

    monkeypatch.setattr(ListAppsOperation, "get_credentials", get_credentials)
    monkeypatch.setattr(list_apps, "GitHubProvider", _Provider)
    return _Provider


def test_list_apps_json_keeps_errors_and_logs_out_of_stdout(run_cli, github):
    result = run_cli("list-apps", "--json")

    assert result.exit_code == 1
    assert "invalid credentials" not in result.stdout
    assert "partial apps" not in result.stdout
    # the organizations that did not fail
    assert json.loads(result.stdout) == [_app("org-b")]
    assert "invalid credentials" in result.stderr
    assert "partial apps of org-b" in result.stderr


def test_list_apps_json_keeps_verbose_output_out_of_stdout(run_cli, github, monkeypatch):
    monkeypatch.setattr(ListAppsOperation, "get_credentials", lambda self, org_config, only_token=False: None)

    result = run_cli("list-apps", "--json", "-v")

    assert result.exit_code == 0
    assert json.loads(result.stdout) == [_app("org-a"), _app("org-b")]
    assert "Listing app installations" in result.stderr
    assert "Found 1 app installations." in result.stderr
    # an info record of _execute_operation
    assert "github api usage for organization 'org-b'" in result.stderr


def test_list_apps_json_writes_nothing_to_stdout_when_the_command_stops(run_cli, github, monkeypatch):
    monkeypatch.setattr(ListAppsOperation, "get_credentials", lambda self, org_config, only_token=False: None)
    monkeypatch.setattr(_Provider, "failing_orgs", ("org-a",))

    result = run_cli("list-apps", "--json")

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "failed retrieving app installations of 'org-a'" in result.stderr


def test_list_apps_json_reports_an_invalid_configuration_on_stderr(run_cli, github, monkeypatch):
    def load_otterdog_config(config_file, local_mode):
        raise RuntimeError("invalid otterdog configuration")

    monkeypatch.setattr(cli, "load_otterdog_config", load_otterdog_config)

    result = run_cli("list-apps", "--json")

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "invalid otterdog configuration" in result.stderr


def test_list_apps_without_json_keeps_messages_on_stdout(run_cli, github):
    # a command with structured output first, its messages must not stay on stderr
    run_cli("list-apps", "--json")

    result = run_cli("list-apps")

    assert result.exit_code == 1
    assert "invalid credentials" in result.stdout
    assert "partial apps of org-b" in result.stdout
    assert "app['org-b-" in result.stdout
    assert result.stderr == ""


@pytest.fixture
def check_status(monkeypatch, tmp_path):
    async def execute(self, org_config, org_index=None, org_count=None) -> int:
        self._print_project_header(org_config, org_index, org_count)
        _logger.warning("partial settings of %s", org_config.github_id)
        self.printer.println("Synchronization status: True")
        self.orgs_status.append({"org_id": org_config.github_id})
        return 0

    monkeypatch.setattr(CheckStatusOperation, "execute", execute)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_check_status_writes_json_to_stdout_with_a_dash(run_cli, check_status):
    result = run_cli("check-status", "--json", "-")

    assert result.exit_code == 0
    assert json.loads(result.stdout) == [{"org_id": "org-a"}, {"org_id": "org-b"}]
    assert "Synchronization status: True" in result.stderr
    assert "partial settings of org-b" in result.stderr
    assert not (check_status / "-").exists()


def test_check_status_writes_json_to_a_file(run_cli, check_status):
    result = run_cli("check-status", "--json", "status.json")

    assert result.exit_code == 0
    assert json.loads((check_status / "status.json").read_text()) == [{"org_id": "org-a"}, {"org_id": "org-b"}]
    assert "Synchronization status: True" in result.stdout
    assert "partial settings of org-b" in result.stdout
    assert result.stderr == ""


def test_check_status_writes_an_empty_list_when_no_organization_was_checked(run_cli, check_status, monkeypatch):
    async def execute(self, org_config, org_index=None, org_count=None) -> int:
        self.printer.print_error(f"invalid credentials for '{org_config.github_id}'")
        return 1

    monkeypatch.setattr(CheckStatusOperation, "execute", execute)

    result = run_cli("check-status", "--json", "-")

    assert result.exit_code == 1
    assert json.loads(result.stdout) == []
    assert "invalid credentials for 'org-b'" in result.stderr

    # a file from an earlier run is replaced
    (check_status / "status.json").write_text(json.dumps([{"org_id": "org-a"}]))

    result = run_cli("check-status", "--json", "status.json")

    assert result.exit_code == 1
    assert json.loads((check_status / "status.json").read_text()) == []
