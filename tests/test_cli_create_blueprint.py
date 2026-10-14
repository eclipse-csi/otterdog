#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import yaml
from click.testing import CliRunner

from otterdog.cli import cli


def test_create_blueprint_writes_validated_file(tmp_path):
    reference = tmp_path / "org.osgi.annotation"
    (reference / ".github" / "workflows").mkdir(parents=True)
    workflow = reference / ".github" / "workflows" / "build.yml"
    workflow.write_text("name: Build\non: [push]\n")
    output = tmp_path / ".eclipsefdn"

    result = CliRunner().invoke(
        cli,
        [
            "create-blueprint",
            "--type",
            "required_file",
            "--blueprint-id",
            "require-build",
            "--filter",
            "^org\\.osgi\\.annotation$",
            "--root",
            str(reference),
            "--from",
            str(workflow),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    target = output / "otterdog" / "blueprints" / "require-build.yml"
    assert target.exists()

    data = yaml.safe_load(target.read_text())
    assert data["id"] == "require-build"
    assert data["config"]["repo_selector"]["name_pattern"] == "^org\\.osgi\\.annotation$"
    assert data["config"]["files"][0]["path"] == ".github/workflows/build.yml"

    # a second run refuses to overwrite without --force
    result = CliRunner().invoke(
        cli, ["create-blueprint", "--type", "required_file", "--blueprint-id", "require-build", "--output", str(output)]
    )
    assert result.exit_code == 1


def test_create_blueprint_rejects_unknown_type(tmp_path):
    result = CliRunner().invoke(
        cli, ["create-blueprint", "--type", "nope", "--blueprint-id", "x", "--output", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert not (tmp_path / "otterdog").exists()
