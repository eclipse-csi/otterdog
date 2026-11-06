#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json

import pytest
from click.testing import CliRunner

from otterdog import cli
from otterdog.config import OtterdogConfig


def _config_file(tmp_path, github_defaults: dict) -> str:
    config_file = tmp_path / "otterdog.json"
    config_file.write_text(
        json.dumps(
            {
                "defaults": {"github": github_defaults},
                "organizations": [],
            }
        )
    )
    return str(config_file)


@pytest.mark.parametrize(
    "github_defaults,expected",
    [({}, False), ({"no_web_ui": False}, False), ({"no_web_ui": True}, True)],
)
def test_default_no_web_ui_of_the_configuration(tmp_path, github_defaults, expected):
    config = OtterdogConfig.from_dict({"defaults": {"github": github_defaults}}, False, str(tmp_path))

    assert config.default_no_web_ui is expected


@pytest.fixture
def run_show_live(tmp_path, monkeypatch):
    operations = []
    monkeypatch.setattr(cli, "_execute_operation", lambda organizations, operation: operations.append(operation))
    # do not reconfigure the logging of the test session
    monkeypatch.setattr(cli, "init_logging", lambda *args, **kwargs: None)

    def run(github_defaults: dict, *args: str) -> bool:
        config_file = _config_file(tmp_path, github_defaults)
        result = CliRunner().invoke(cli.cli, ["show-live", "-c", config_file, *args])

        assert result.exit_code == 0, result.output
        return operations[-1].no_web_ui

    return run


@pytest.mark.parametrize(
    "github_defaults,args,expected",
    [
        ({}, [], False),
        ({}, ["-n"], True),
        ({}, ["--no-web-ui"], True),
        ({"no_web_ui": True}, [], True),
        ({"no_web_ui": True}, ["-n"], True),
        ({"no_web_ui": True}, ["--web-ui"], False),
        ({"no_web_ui": False}, ["--no-web-ui"], True),
    ],
)
def test_no_web_ui_defaults_to_the_configuration_and_can_be_overridden(run_show_live, github_defaults, args, expected):
    assert run_show_live(github_defaults, *args) is expected
