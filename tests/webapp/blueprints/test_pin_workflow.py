#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from dataclasses import fields
from unittest import mock

import yaml

from otterdog.models.repository import Repository
from otterdog.webapp.blueprints import BlueprintType, read_blueprint
from otterdog.webapp.blueprints.pin_workflow import PinWorkflowBlueprint

yaml_content = """
id: pin-workflows
name: Pin all workflows
type: pin_workflow
config:
  repo_selector:
    name_pattern: .github
"""

multiple_repo_selection = """
id: pin-workflows
type: pin_workflow
config:
    repo_selector:
      name_pattern:
        - .github
        - repo-1
        - repo-2
        - repo-3
"""

no_repo_selection = """
id: pin-workflows
type: pin_workflow
"""


def test_read():
    config = yaml.safe_load(yaml_content)

    blueprint = read_blueprint("a", config)
    assert blueprint.type == BlueprintType.PIN_WORKFLOW

    assert isinstance(blueprint, PinWorkflowBlueprint)


def test_repo_selector_multiple_repos():
    config = yaml.safe_load(multiple_repo_selection)

    blueprint = read_blueprint("a", config)
    assert blueprint.type == BlueprintType.PIN_WORKFLOW

    assert isinstance(blueprint, PinWorkflowBlueprint)

    selector = blueprint.repo_selector

    assert selector.matches(create_repo_with_name(".github"))
    assert selector.matches(create_repo_with_name("repo-1"))
    assert selector.matches(create_repo_with_name("repo-10")) is False


def test_no_repo_selector():
    config = yaml.safe_load(no_repo_selection)

    blueprint = read_blueprint("a", config)
    assert blueprint.type == BlueprintType.PIN_WORKFLOW

    assert isinstance(blueprint, PinWorkflowBlueprint)

    selector = blueprint.repo_selector

    assert selector is None

    assert blueprint._matches(create_repo_with_name(".github"))
    assert blueprint._matches(create_repo_with_name("repo-1"))
    assert blueprint._matches(create_repo_with_name("repo-10"))


def create_repo_with_name(name: str) -> Repository:
    repo = create_dataclass_mock(Repository)
    repo.name = name
    return repo


def create_dataclass_mock(obj):
    return mock.Mock(spec_set=[field.name for field in fields(obj)])
