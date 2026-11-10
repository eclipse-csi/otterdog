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


@pytest.fixture
def run(tmp_path, monkeypatch):
    operations = []
    monkeypatch.setattr(cli, "_execute_operation", lambda organizations, operation: operations.append(operation))
    # do not reconfigure the logging of the test session
    monkeypatch.setattr(cli, "init_logging", lambda *args, **kwargs: None)
    config_file = tmp_path / "otterdog.json"
    config_file.write_text(json.dumps({"defaults": {}, "organizations": []}))

    def invoke(*args: str):
        result = CliRunner().invoke(cli.cli, [args[0], "-c", str(config_file), *args[1:]])
        return result, operations[-1] if operations else None

    return invoke


@pytest.mark.parametrize("command", ["apply", "local-apply"])
def test_delete_filter_narrows_the_deleted_resources(run, command):
    result, operation = run(
        command, "-d", "--delete-filter", "org_code_security_configuration", "--delete-filter", "team_sync"
    )

    assert result.exit_code == 0, result.output
    assert operation.delete_resources() is True
    assert [str(x) for x in operation.delete_filter()] == ["org_code_security_configuration", "team_sync"]


@pytest.mark.parametrize("command", ["apply", "local-apply"])
def test_without_delete_filter_all_resources_are_deleted(run, command):
    result, operation = run(command, "-d")

    assert result.exit_code == 0, result.output
    assert operation.delete_filter() == ()


@pytest.mark.parametrize("command", ["apply", "local-apply"])
def test_delete_filter_requires_delete_resources(run, command):
    result, operation = run(command, "--delete-filter", "org_code_security_configuration")

    assert result.exit_code == 2
    assert "option '--delete-filter' requires '--delete-resources'" in result.output
    assert operation is None


@pytest.mark.parametrize("command", ["apply", "local-apply"])
def test_delete_filter_selects_resources_by_key(run, command):
    selector = 'org_code_security_configuration[name="Legacy - private/internal repositories"]'
    result, operation = run(command, "-d", "--delete-filter", selector)

    assert result.exit_code == 0, result.output
    (parsed,) = operation.delete_filter()
    assert parsed.conditions == (("name", "Legacy - private/internal repositories"),)


@pytest.mark.parametrize("selector", ["", "org_variable[]", 'org_variable[name="a" b]', "org_variable[=a]"])
def test_invalid_delete_filter_is_rejected(run, selector):
    result, operation = run("apply", "-d", "--delete-filter", selector)

    assert result.exit_code == 2
    assert "invalid resource selector" in result.output
    assert operation is None
