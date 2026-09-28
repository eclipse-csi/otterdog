#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
from copy import deepcopy
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock

import pretend

from otterdog.config import OrganizationConfig
from otterdog.jsonnet import JsonnetConfig
from otterdog.models.github_organization import GitHubOrganization
from otterdog.operations.apply import ApplyOperation
from otterdog.operations.check_status import CheckStatusOperation
from otterdog.operations.local_plan import LocalPlanOperation
from otterdog.operations.validate import ValidationStatus
from otterdog.utils import IndentingPrinter, LogLevel

_BASE_TEMPLATE = "https://github.com/otterdog/test-defaults#test-defaults.libsonnet@main"


def _create_org_config(tmp_path: Path, with_config_files: bool, base_differs: bool = True) -> OrganizationConfig:
    """Create a local-only organization config and, when requested, its desired and BASE files.

    The desired file describes the configuration being planned. The BASE file represents the live
    configuration and can differ in one repository description, giving the operation an observable
    change to report without contacting GitHub.
    """
    jsonnet_config = JsonnetConfig("test-org", str(tmp_path), _BASE_TEMPLATE, local_only=True)
    Path(jsonnet_config.template_file).parent.mkdir(parents=True)
    Path(jsonnet_config.template_file).write_text("{}", encoding="utf-8")

    if with_config_files:
        resource_file = Path(__file__).parents[1] / "models" / "resources" / "otterdogtest.json"
        expected_data = json.loads(resource_file.read_text(encoding="utf-8"))
        expected_data["project_name"] = "test-project"
        expected_data["github_id"] = "test-org"

        current_data = deepcopy(expected_data)
        if base_differs:
            current_data["repositories"][0]["description"] = "changed in GitHub"

        config_file = Path(jsonnet_config.org_config_file)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps(expected_data), encoding="utf-8")
        Path(f"{config_file}-BASE").write_text(json.dumps(current_data), encoding="utf-8")

    return OrganizationConfig(
        "test-project",
        "test-org",
        ".config",
        _BASE_TEMPLATE,
        jsonnet_config,
        {},
    )


def _initialize_operation(operation, monkeypatch, output: StringIO, client, current_org=None):
    """
    Initialize an operation while replacing only GitHub and validation boundaries.
    """
    monkeypatch.setattr(operation, "setup_github_client", lambda org_config: client)
    monkeypatch.setattr(operation, "validate", AsyncMock(return_value=ValidationStatus()))
    if current_org is not None:
        monkeypatch.setattr(operation, "load_current_org", AsyncMock(return_value=current_org))

    operation.init(pretend.stub(exclude_teams_pattern=None), IndentingPrinter(output, log_level=LogLevel.ERROR))


async def test_local_plan_reports_changes_for_a_configuration_difference(tmp_path, monkeypatch):
    """
    A local plan reports the difference between the desired and BASE configurations.
    """
    org_config = _create_org_config(tmp_path, with_config_files=True)
    output = StringIO()
    operation = LocalPlanOperation("-BASE", "*", False, False, False, "")
    client = pretend.stub(close=AsyncMock())
    _initialize_operation(operation, monkeypatch, output, client)

    result = await operation.execute(org_config)

    assert result == 0
    assert "1 to change" in output.getvalue()


async def test_local_plan_returns_failure_when_the_configuration_is_missing(tmp_path, monkeypatch):
    """
    A local plan returns failure and explains when the desired configuration is absent.
    """
    org_config = _create_org_config(tmp_path, with_config_files=False)
    output = StringIO()
    operation = LocalPlanOperation("-BASE", "*", False, False, False, "")
    client = pretend.stub(close=AsyncMock())
    _initialize_operation(operation, monkeypatch, output, client)

    result = await operation.execute(org_config)

    assert result == 1
    assert "does not yet exist" in output.getvalue()


async def test_apply_reports_no_changes_for_matching_configurations(tmp_path, monkeypatch):
    """
    Apply keeps its user-visible no-op behavior when the desired and live configurations match.
    """
    org_config = _create_org_config(tmp_path, with_config_files=True, base_differs=False)
    expected_org = GitHubOrganization.load_from_file(org_config.github_id, org_config.jsonnet_config.org_config_file)
    output = StringIO()
    operation = ApplyOperation(True, True, "*", False, False, False, "", False)
    client = pretend.stub(close=AsyncMock())
    _initialize_operation(operation, monkeypatch, output, client, expected_org)

    result = await operation.execute(org_config)

    assert result == 0
    assert "No changes required." in output.getvalue()


async def test_apply_processes_a_non_empty_plan(tmp_path, monkeypatch):
    """
    Apply executes the generated patch and reports the completed plan.
    """
    org_config = _create_org_config(tmp_path, with_config_files=True)
    current_org = GitHubOrganization.load_from_file(
        org_config.github_id, f"{org_config.jsonnet_config.org_config_file}-BASE"
    )
    output = StringIO()
    update_repo = AsyncMock()
    operation = ApplyOperation(True, True, "*", False, False, False, "", False)
    client = pretend.stub(close=AsyncMock(), update_repo=update_repo)
    _initialize_operation(operation, monkeypatch, output, client, current_org)

    result = await operation.execute(org_config)

    assert result == 0
    assert "Executed plan" in output.getvalue()
    update_repo.assert_awaited_once()


async def test_check_status_reports_the_status_of_matching_configurations(tmp_path, monkeypatch):
    """
    Check-status exposes a valid, in-sync result when the desired and live configurations match.
    """
    org_config = _create_org_config(tmp_path, with_config_files=True, base_differs=False)
    expected_org = GitHubOrganization.load_from_file(org_config.github_id, org_config.jsonnet_config.org_config_file)
    output = StringIO()
    archived_check = AsyncMock(return_value=False)
    client = pretend.stub(
        close=AsyncMock(),
        rest_api=pretend.stub(org=pretend.stub(is_archived=archived_check)),
    )
    operation = CheckStatusOperation(True, "*")
    _initialize_operation(operation, monkeypatch, output, client, expected_org)

    result = await operation.execute(org_config)

    assert result == 0
    assert operation.orgs_status == [
        {
            "org_id": "test-org",
            "is_archived": False,
            "validation_status": {
                "is_valid": True,
                "infos": 0,
                "warnings": 0,
                "errors": 0,
            },
            "sync_status": {
                "in_sync": True,
                "additions": 0,
                "changes": 0,
                "deletions": 0,
            },
        }
    ]
    archived_check.assert_awaited_once_with("test-org")
