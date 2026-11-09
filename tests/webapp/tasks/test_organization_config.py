#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from otterdog.config import OtterdogConfig
from otterdog.webapp.tasks import get_organization_config

_DEFAULTS = Path(__file__).parents[3] / "otterdog" / "resources" / "defaults" / "otterdog-defaults.libsonnet"


def _otterdog_config(tmp_path, unmanaged) -> OtterdogConfig:
    return OtterdogConfig.from_dict(
        {
            "defaults": {"jsonnet": {"base_template": str(_DEFAULTS)}},
            "organizations": [
                {
                    "name": "my-project",
                    "github_id": "my-org",
                    "credentials": {"provider": "plain"},
                    "unmanaged": unmanaged,
                }
            ],
        },
        False,
        str(tmp_path),
    )


def _installation(project_name="my-project"):
    return SimpleNamespace(
        project_name=project_name, github_id="my-org", config_repo=".otterdog", base_template=str(_DEFAULTS)
    )


async def test_the_organization_config_has_the_unmanaged_paths_of_the_otterdog_config(monkeypatch, tmp_path):
    config = _otterdog_config(tmp_path, ["repository.workflows.max_cache_size_gb", "organization.codespaces_secrets"])
    monkeypatch.setattr("otterdog.webapp.utils.get_otterdog_config", AsyncMock(return_value=config))

    org_config = await get_organization_config(_installation(), "token", str(tmp_path), str(tmp_path))

    assert org_config.jsonnet_config.unmanaged == frozenset(
        {"repository.workflows.max_cache_size_gb", "organization.codespaces_secrets"}
    )
    assert org_config.jsonnet_config.unmanaged_error is None


async def test_the_organization_config_reports_an_invalid_list_of_the_otterdog_config(monkeypatch, tmp_path):
    config = _otterdog_config(tmp_path, ["repository.nope"])
    monkeypatch.setattr("otterdog.webapp.utils.get_otterdog_config", AsyncMock(return_value=config))

    org_config = await get_organization_config(_installation(), "token", str(tmp_path), str(tmp_path))

    assert org_config.jsonnet_config.unmanaged == frozenset()
    assert "'repository.nope' is not a setting or resource" in org_config.jsonnet_config.unmanaged_error


async def test_nothing_is_unmanaged_for_a_project_that_the_otterdog_config_does_not_define(monkeypatch, tmp_path):
    config = _otterdog_config(tmp_path, ["team.team_sync"])
    monkeypatch.setattr("otterdog.webapp.utils.get_otterdog_config", AsyncMock(return_value=config))

    org_config = await get_organization_config(_installation("other-project"), "token", str(tmp_path), str(tmp_path))

    assert org_config.jsonnet_config.unmanaged == frozenset()
    assert org_config.jsonnet_config.unmanaged_error is None
