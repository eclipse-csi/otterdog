# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from typing import Any

from jsonbender import bend, K, S, OptionalS

from . import schemas
from .github import Github


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


def map_github_org_webhook_data_to_otterdog(github_org_webhook_data: dict[str, Any]) -> dict[str, Any]:
    allowed_webhook_properties = schemas.get_properties_of_schema(schemas.WEBHOOK_SCHEMA)

    # first create an identity mapping for all properties contained in the schema.
    mapping = {}
    for k in allowed_webhook_properties:
        if k in github_org_webhook_data:
            mapping[k] = S(k)

    # add mapping for specific properties if they are present.
    if "config" in github_org_webhook_data:
        mapping.update({
            "url": S("config", "url"),
            "content_type": S("config", "content_type"),
            "insecure_ssl": S("config", "insecure_ssl"),
            "secret": OptionalS("config", "secret"),
        })

    return bend(mapping, github_org_webhook_data)


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


def map_github_branch_protection_rule_data_to_otterdog(github_bpr_data: dict[str, Any]) -> dict[str, Any]:
    allowed_bpr_properties = schemas.get_properties_of_schema(schemas.BRANCH_PROTECTION_RULE_SCHEMA)

    # first create an identity mapping for all properties contained in the schema.
    mapping = {}
    for k in allowed_bpr_properties:
        if k in github_bpr_data:
            mapping[k] = S(k)

    return bend(mapping, github_bpr_data)


def map_otterdog_org_settings_data_to_github(otterdog_org_data: dict[str, Any]) -> dict[str, Any]:
    allowed_repo_properties = schemas.get_properties_of_schema(schemas.SETTINGS_SCHEMA)

    # first create an identity mapping for all properties contained in the schema.
    mapping = {}
    for k in allowed_repo_properties:
        if k in otterdog_org_data:
            mapping[k] = S(k)

    # plan is a readonly feature only needed for validation.
    if "plan" in otterdog_org_data:
        mapping.pop("plan")

    return bend(mapping, otterdog_org_data)


def map_otterdog_org_webhook_data_to_github(otterdog_webhook_data: dict[str, Any]) -> dict[str, Any]:
    allowed_webhook_properties = schemas.get_properties_of_schema(schemas.WEBHOOK_SCHEMA)

    # first create an identity mapping for all properties contained in the schema.
    mapping = {}
    for k in allowed_webhook_properties:
        if k in otterdog_webhook_data:
            mapping[k] = S(k)

    config_mapping = {}
    for config_prop in ["url", "content_type", "insecure_ssl", "secret"]:
        if config_prop in mapping:
            mapping.pop(config_prop)
        if config_prop in otterdog_webhook_data:
            config_mapping[config_prop] = S(config_prop)

    if len(config_mapping) > 0:
        mapping.update({"config": config_mapping})

    return bend(mapping, otterdog_webhook_data)


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


def map_otterdog_branch_protection_rule_data_to_github(otterdog_bpr_data: dict[str, Any],
                                                       gh_client: Github) -> dict[str, Any]:
    allowed_bpr_properties = schemas.get_properties_of_schema(schemas.BRANCH_PROTECTION_RULE_SCHEMA)

    # first create an identity mapping for all properties contained in the schema.
    mapping = {}
    for k in allowed_bpr_properties:
        if k in otterdog_bpr_data:
            mapping[k] = S(k)

    if "pushRestrictions" in otterdog_bpr_data:
        mapping.pop("pushRestrictions")
        restricts_pushes = otterdog_bpr_data["pushRestrictions"]
        if restricts_pushes is not None:
            actor_ids = gh_client.get_actor_ids(restricts_pushes)
            mapping["pushActorIds"] = K(actor_ids)
            mapping["restrictsPushes"] = K(True if len(actor_ids) > 0 else False)

    if "reviewDismissalAllowances" in otterdog_bpr_data:
        mapping.pop("reviewDismissalAllowances")
        review_dismissal_allowances = otterdog_bpr_data["reviewDismissalAllowances"]
        if review_dismissal_allowances is not None:
            actor_ids = gh_client.get_actor_ids(review_dismissal_allowances)
            mapping["reviewDismissalActorIds"] = K(actor_ids)

    return bend(mapping, otterdog_bpr_data)
