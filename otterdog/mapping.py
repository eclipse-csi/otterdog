# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import re
from typing import Any

from jsonbender import bend, K, S

from . import schemas
from .providers.github import Github

# TODO: move these methods to the respective model class in an method to_provider


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

    if "bypassPullRequestAllowances" in otterdog_bpr_data:
        mapping.pop("bypassPullRequestAllowances")
        bypass_pull_request_allowances = otterdog_bpr_data["bypassPullRequestAllowances"]
        if bypass_pull_request_allowances is not None:
            actor_ids = gh_client.get_actor_ids(bypass_pull_request_allowances)
            mapping["bypassPullRequestActorIds"] = K(actor_ids)

    if "bypassForcePushAllowances" in otterdog_bpr_data:
        mapping.pop("bypassForcePushAllowances")
        bypass_force_push_allowances = otterdog_bpr_data["bypassForcePushAllowances"]
        if bypass_force_push_allowances is not None:
            actor_ids = gh_client.get_actor_ids(bypass_force_push_allowances)
            mapping["bypassForcePushActorIds"] = K(actor_ids)

    if "requiredStatusChecks" in otterdog_bpr_data:
        mapping.pop("requiredStatusChecks")
        required_status_checks = otterdog_bpr_data["requiredStatusChecks"]
        if required_status_checks is not None:
            app_slugs = set()

            for check in required_status_checks:
                if ":" in check:
                    app_slug, context = re.split(":", check, 1)

                    if app_slug != "any":
                        app_slugs.add(app_slug)
                else:
                    app_slugs.add("github-actions")

            app_ids = gh_client.get_app_ids(app_slugs)

            transformed_checks = []
            for check in required_status_checks:
                if ":" in check:
                    app_slug, context = re.split(":", check, 1)
                else:
                    app_slug = "github-actions"
                    context = check

                if app_slug == "any":
                    transformed_checks.append({"appId": "any", "context": context})
                else:
                    transformed_checks.append({"appId": app_ids[app_slug], "context": context})

            mapping["requiredStatusChecks"] = K(transformed_checks)

    return bend(mapping, otterdog_bpr_data)
