# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from typing import Any

from jsonbender import bend, S

from . import schemas


_FIELDS_NOT_AVAILABE_FOR_ARCHIVED_PROJECTS =\
    {
        "allow_auto_merge",
        "allow_merge_commit",
        "allow_rebase_merge",
        "allow_squash_merge",
        "allow_update_branch",
        "delete_branch_on_merge",
        "merge_commit_message",
        "merge_commit_title",
        "squash_merge_commit_message",
        "squash_merge_commit_title"
    }


def shall_repo_key_be_included(key: str, is_private: bool, is_archived: bool) -> bool:
    if is_private and (key == "secret_scanning"):
        return False

    if is_archived:
        if key in _FIELDS_NOT_AVAILABE_FOR_ARCHIVED_PROJECTS:
            return False

    return True


def map_github_org_settings_data_to_otterdog(github_org_data: dict[str, Any]) -> dict[str, Any]:
    allowed_repo_properties = schemas.get_properties_of_schema(schemas.SETTINGS_SCHEMA)

    # first create an identity mapping for all properties contained in the schema.
    mapping = {}
    for k in allowed_repo_properties:
        if k in github_org_data:
            mapping[k] = S(k)

    # add mapping for specific properties if they are present.
    if "plan" in github_org_data:
        mapping.update({
            "plan": S("plan", "name")
        })

    return bend(mapping, github_org_data)


def map_github_repo_data_to_otterdog(github_repo_data: dict[str, Any]) -> dict[str, Any]:
    allowed_repo_properties = schemas.get_properties_of_schema(schemas.REPOSITORY_SCHEMA)

    # first create an identity mapping for all properties contained in the schema.
    mapping = {}
    for k in allowed_repo_properties:
        if k in github_repo_data:
            mapping[k] = S(k)

    # add mapping for specific properties if they are present.
    # the "security_and_analysis is not present for private repos.
    if "security_and_analysis" in github_repo_data:
        mapping.update({
            "secret_scanning": S("security_and_analysis", "secret_scanning", "status"),
            "secret_scanning_push_protection": S("security_and_analysis", "secret_scanning_push_protection", "status")
        })

    return bend(mapping, github_repo_data)


def map_otterdog_org_settings_data_to_github(otterdog_org_data: dict[str, Any]) -> dict[str, Any]:
    allowed_repo_properties = schemas.get_properties_of_schema(schemas.SETTINGS_SCHEMA)

    # first create an identity mapping for all properties contained in the schema.
    mapping = {}
    for k in allowed_repo_properties:
        if k in otterdog_org_data:
            mapping[k] = S(k)

    # plan is a readonly feature only needed for validation.
    mapping.pop("plan")

    return bend(mapping, otterdog_org_data)


def map_otterdog_repo_data_to_github(otterdog_repo_data: dict[str, Any]) -> dict[str, Any]:
    allowed_repo_properties = schemas.get_properties_of_schema(schemas.REPOSITORY_SCHEMA)

    # first create an identity mapping for all properties contained in the schema.
    mapping = {}
    for k in allowed_repo_properties:
        if k in otterdog_repo_data:
            mapping[k] = S(k)

    # add mapping for items that GitHub expects in a nested structure.
    is_private = otterdog_repo_data.get("private", False)

    # private repos don't support a security_and_analysis block.
    if is_private:
        for security_prop in ["secret_scanning", "secret_scanning_push_protection"]:
            if security_prop in mapping:
                mapping.pop(security_prop)
    else:
        security_mapping = {}
        for security_prop in ["secret_scanning", "secret_scanning_push_protection"]:
            if security_prop in mapping:
                mapping.pop(security_prop)
            if security_prop in otterdog_repo_data:
                security_mapping[security_prop] = {"status": S(security_prop)}

        if len(security_mapping) > 0:
            mapping.update({"security_and_analysis": security_mapping})

    return bend(mapping, otterdog_repo_data)
