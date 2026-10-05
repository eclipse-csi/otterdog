#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pytest
import yaml

from otterdog.webapp.blueprints import read_blueprint
from otterdog.webapp.blueprints.scaffold import (
    PLACEHOLDER_FILE,
    UnknownBlueprintTypeError,
    default_blueprint_id,
    exact_name_pattern,
    render_blueprint_yaml,
    scaffold_blueprint,
    valid_blueprint_types,
)

WORKFLOW = "name: Build\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make\n"


def test_valid_types():
    assert valid_blueprint_types() == ["required_file", "pin_workflow", "append_configuration", "scorecard_integration"]


def test_unknown_type_lists_valid_ones():
    with pytest.raises(UnknownBlueprintTypeError) as ex:
        scaffold_blueprint("nope", "x", None, {})
    assert "required_file" in str(ex.value)


def test_exact_name_pattern_escapes_dots():
    import re

    pattern = exact_name_pattern("org.osgi.annotation")
    assert re.fullmatch(pattern, "org.osgi.annotation")
    assert not re.fullmatch(pattern, "org-osgi-annotation")


@pytest.mark.parametrize(
    "blueprint_type, files, expected",
    [
        ("required_file", {".github/workflows/build.yml": "x"}, "require-build"),
        ("required_file", {}, "required-file"),
        ("scorecard_integration", {}, "scorecard-integration"),
        ("required_file", {"docs/My File.md": "x"}, "require-my-file"),
    ],
)
def test_default_blueprint_id(blueprint_type, files, expected):
    assert default_blueprint_id(blueprint_type, files) == expected


def test_required_file_from_files_round_trips_through_yaml():
    data = scaffold_blueprint(
        "required_file",
        "require-build",
        "^org\\.osgi\\.annotation$",
        {".github/workflows/build.yml": WORKFLOW},
        description="desc",
    )
    rendered = render_blueprint_yaml(data)

    # multi-line content is rendered as a literal block, like hand-written blueprints
    assert "content: |" in rendered

    reloaded = yaml.safe_load(rendered)
    blueprint = read_blueprint("otterdog/blueprints/require-build.yml", reloaded)
    assert blueprint.id == "require-build"
    assert blueprint.type.value == "required_file"
    assert blueprint.repo_selector.name_pattern == "^org\\.osgi\\.annotation$"
    assert blueprint.files[0].path == ".github/workflows/build.yml"
    assert blueprint.files[0].content == WORKFLOW
    assert blueprint.files[0].strict is False


def test_required_file_without_files_gets_placeholder():
    data = scaffold_blueprint("required_file", "x", None, {})
    assert data["config"]["files"][0]["path"] == PLACEHOLDER_FILE
    assert "repo_selector" not in data["config"]


def test_scorecard_integration_takes_first_file_as_workflow():
    data = scaffold_blueprint("scorecard_integration", "sc", None, {".github/workflows/scorecard.yml": WORKFLOW})
    assert data["config"]["workflow_name"] == "scorecard.yml"
    assert data["config"]["workflow_content"] == WORKFLOW
    read_blueprint("p", data)


def test_pin_workflow_and_append_configuration_validate():
    read_blueprint("p", scaffold_blueprint("pin_workflow", "pin", ["a", "b"], {}))
    read_blueprint("p", scaffold_blueprint("append_configuration", "append", "ignored", {}))
