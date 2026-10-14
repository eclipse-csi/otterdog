#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""
Scaffolding of blueprint definitions, shared by the CLI command `create-blueprint` and the
comment command `/otterdog create blueprint`.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from otterdog.webapp.blueprints import BLUEPRINT_PATH, Blueprint, BlueprintType, read_blueprint

PLACEHOLDER_FILE = ".github/CHANGE-ME.md"
PLACEHOLDER_CONTENT = "# TODO\n\nReplace this file with the content the blueprint should roll out.\n"


class UnknownBlueprintTypeError(ValueError):
    def __init__(self, blueprint_type: str):
        super().__init__(
            f"unknown blueprint type '{blueprint_type}', valid types: {', '.join(valid_blueprint_types())}"
        )
        self.blueprint_type = blueprint_type


def valid_blueprint_types() -> list[str]:
    return [t.value for t in BlueprintType]


_BLUEPRINT_ID_PATTERN = re.compile(r"[\w.-]+")


def is_valid_blueprint_id(blueprint_id: str) -> bool:
    """A blueprint id is also the file name, the branch name and part of the labels: keep it flat and simple."""
    return _BLUEPRINT_ID_PATTERN.fullmatch(blueprint_id) is not None and blueprint_id not in (".", "..")


def blueprint_file_path(blueprint_id: str) -> str:
    return f"{BLUEPRINT_PATH}/{blueprint_id}.yml"


def exact_name_pattern(repo_name: str) -> str:
    """A selector that matches exactly one repository, the narrow start of a staged rollout."""
    return f"^{re.escape(repo_name)}$"


def default_blueprint_id(blueprint_type: str, files: dict[str, str]) -> str:
    if len(files) > 0:
        first = next(iter(files))
        stem = first.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        base = f"require-{stem}"
    else:
        base = blueprint_type.replace("_", "-")
    return re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-").lower()


def scaffold_blueprint(
    blueprint_type: str,
    blueprint_id: str,
    name_pattern: str | list[str] | None,
    files: dict[str, str],
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """
    Builds the data of a blueprint definition and validates it against the blueprint model.

    :raises UnknownBlueprintTypeError: for an unsupported type
    :raises ValueError: for a definition that does not validate
    """
    try:
        resolved_type = BlueprintType(blueprint_type)
    except ValueError as ex:
        raise UnknownBlueprintTypeError(blueprint_type) from ex

    config: dict[str, Any] = {}
    if name_pattern is not None and resolved_type != BlueprintType.APPEND_CONFIGURATION:
        config["repo_selector"] = {"name_pattern": name_pattern}

    # pin_workflow needs nothing beyond the selector
    match resolved_type:
        case BlueprintType.REQUIRED_FILE:
            file_entries = files if len(files) > 0 else {PLACEHOLDER_FILE: PLACEHOLDER_CONTENT}
            config["files"] = [
                {"path": path, "content": content, "strict": False} for path, content in file_entries.items()
            ]

        case BlueprintType.SCORECARD_INTEGRATION:
            if len(files) > 0:
                path, content = next(iter(files.items()))
                config["workflow_name"] = path.rsplit("/", 1)[-1]
                config["workflow_content"] = content
            else:
                config["workflow_content"] = PLACEHOLDER_CONTENT

        case BlueprintType.APPEND_CONFIGURATION:
            config["condition"] = "$.repositories[?(@.name == 'CHANGE-ME')]"
            config["content"] = "# TODO: jsonnet snippet appended to the configuration\n{}"

    data: dict[str, Any] = {
        "id": blueprint_id,
        "name": name if name is not None else f"Blueprint {blueprint_id}",
    }
    if description is not None:
        data["description"] = description
    data["type"] = resolved_type.value
    data["config"] = config

    validate_blueprint_data(data)
    return data


def validate_blueprint_data(data: dict[str, Any]) -> Blueprint:
    """Round-trips the data through the blueprint model, raising ValueError on invalid definitions."""
    try:
        return read_blueprint(blueprint_file_path(data["id"]), data)
    except (KeyError, RuntimeError, ValueError) as ex:
        raise ValueError(f"blueprint definition does not validate: {ex}") from ex


class _BlueprintDumper(yaml.SafeDumper):
    pass


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    # multi-line strings (file contents) as literal blocks, which is how blueprints are written by hand
    if "\n" in value:
        return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", value)


_BlueprintDumper.add_representer(str, _represent_str)


def render_blueprint_yaml(data: dict[str, Any]) -> str:
    return yaml.dump(data, Dumper=_BlueprintDumper, sort_keys=False, allow_unicode=True, width=120)
