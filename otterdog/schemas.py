# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
from importlib_resources import files
from typing import Any

ORG_SCHEMA = json.loads(files("resources").joinpath("schemas/organization.json").read_text())
SETTINGS_SCHEMA = json.loads(files("resources").joinpath("schemas/settings.json").read_text())
WEBHOOK_SCHEMA = json.loads(files("resources").joinpath("schemas/webhook.json").read_text())
REPOSITORY_SCHEMA = json.loads(files("resources").joinpath("schemas/repository.json").read_text())
BRANCH_PROTECTION_RULE_SCHEMA = json.loads(files("resources").joinpath("schemas/branch-protection-rule.json").read_text())


def add_items_if_contained_in_schema(data: dict[str, Any], schema: dict[str, Any], result: dict[str, Any]) -> None:
    properties = schema["properties"]
    for k, v in data.items():
        if k in properties:
            if isinstance(v, dict):
                nested_result = {}
                add_items_if_contained_in_schema(v, properties[k], nested_result)
                result[k] = nested_result
            else:
                result[k] = v


def get_items_contained_in_schema(data: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    result = {}
    add_items_if_contained_in_schema(data, schema, result)
    return result


def get_properties_of_schema(schema: dict[str, Any]) -> set[str]:
    properties = set()
    for k, v in schema["properties"].items():
        properties.add(k)
    return properties
