# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
import os
import textwrap
from io import StringIO
from typing import Any

import _jsonnet
import jsonschema
from importlib_resources import files, as_file

import schemas
import utils
from config import JsonnetConfig
from github import Github


class Organization:
    def __init__(self, github_id: str):
        self.github_id = github_id
        self._dict = {}

    def load_config(self, data: dict[str, Any]) -> None:
        self._validate_org_config(data)
        self._dict.clear()
        self._dict.update(data)

    def get_settings(self) -> dict[str, Any]:
        return self._dict.get("settings")

    def update_settings(self, data: dict[str, Any]) -> None:
        values = schemas.get_items_contained_in_schema(data, schemas.SETTINGS_SCHEMA)
        utils.print_debug("updating settings to " + json.dumps(values, indent=2))
        self._dict["settings"] = values

    def get_webhooks(self) -> list[dict[str, Any]]:
        return self._dict.get("webhooks", [])

    def update_webhooks(self, webhooks: list[dict[str, Any]]) -> None:
        clean_webhooks = []
        for webhook in webhooks:
            clean_webhooks.append(schemas.get_items_contained_in_schema(webhook, schemas.WEBHOOK_SCHEMA))

        utils.print_debug("updating webhooks to " + json.dumps(clean_webhooks, indent=2))

        self._dict["webhooks"] = clean_webhooks

    def get_repos(self) -> list[dict[str, Any]]:
        return self._dict.get("repositories", [])

    def update_repos(self, repos: list[dict[str, Any]]) -> None:
        clean_repos = []
        for repo in repos:
            clean_repos.append(schemas.get_items_contained_in_schema(repo, schemas.REPOSITORY_SCHEMA))

        utils.print_debug("updating repos to " + json.dumps(clean_repos, indent=2))

        self._dict["repositories"] = clean_repos

    def validate(self) -> None:
        self._validate_org_config(self._dict)

    @staticmethod
    def _validate_org_config(data: dict[str, Any]) -> None:
        with as_file(files("resources").joinpath("schemas")) as resource_dir:
            schema_root = resource_dir.as_uri()
            resolver = jsonschema.validators.RefResolver(base_uri=f"{schema_root}/", referrer=data)
            jsonschema.validate(instance=data, schema=schemas.ORG_SCHEMA, resolver=resolver)

    def write_jsonnet_config(self, config: JsonnetConfig) -> str:
        default_config = config.default_org_config

        output = StringIO()
        output.write(textwrap.dedent(f"""
            local orgs = {config.get_import_statement()};

            orgs.newOrg('{self.github_id}') {{
                settings+: {{
        """))

        settings = self.get_settings()
        default_org_settings = default_config["settings"]
        for key, default_value in sorted(default_org_settings.items()):
            if key not in settings:
                utils.print_warn(f"unexpected key '{key}' found in default configuration, skipping")
                continue

            current_value = settings[key]
            if current_value != default_value:
                output.write("      {}: {},\n".format(key, json.dumps(current_value)))

        output.write("    },\n")

        webhooks = self.get_webhooks()
        if len(webhooks) > 0:
            default_org_webhook = config.default_org_webhook_config
            output.write("    webhooks+: [\n")
            for webhook in webhooks:
                diff_obj = utils.get_diff_from_defaults(webhook, default_org_webhook)
                output.write("      orgs.newWebhook() ")
                utils.dump_json_object(diff_obj, output, offset=6, indent=2, embedded_object=True)

            output.write("    ],\n")

        repos = self.get_repos()
        if len(repos) > 0:
            default_org_repo = config.default_org_repo_config
            output.write("    repositories+: [\n")
            for repo in repos:
                diff_obj = utils.get_diff_from_defaults(repo, default_org_repo)

                # remove the name key from the diff_obj to avoid serializing it to json
                name = repo["name"]
                diff_obj.pop("name")

                output.write(f"      orgs.newRepo('{name}') ")

                def is_branch_protection_rule_key(k):
                    return k == "branch_protection_rules"

                def dump_branch_protection_rule(k, v, o):
                    default_org_rule = config.default_org_branch_config
                    output.write("branch_protection_rules: [\n")
                    o += 2
                    for rule in v:
                        rule_diff = utils.get_diff_from_defaults(rule, default_org_rule)

                        pattern = rule["pattern"]
                        rule_diff.pop("pattern")

                        output.write(" " * o)
                        output.write(f"orgs.newBranchProtectionRule('{pattern}') ")
                        utils.dump_json_object(rule_diff, output, offset=o, indent=2, embedded_object=True)

                    o -= 2
                    output.write(" " * o)
                    output.write("]\n")

                utils.dump_json_object(diff_obj, output, offset=6, indent=2, embedded_object=True,
                                       predicate=is_branch_protection_rule_key,
                                       func=dump_branch_protection_rule)

            output.write("    ]\n")

        output.write("}")
        return output.getvalue()

    def __str__(self) -> str:
        return f"Organization(id={self.github_id})"


def load_from_file(github_id: str, config_file: str) -> Organization:
    if not os.path.exists(config_file):
        msg = f"configuration file '{config_file}' for organization '{github_id}' does not exist"
        raise RuntimeError(msg)

    config = json.loads(_jsonnet.evaluate_file(config_file))
    org = Organization(github_id)
    org.load_config(config)
    return org


def load_from_github(github_id: str, client: Github) -> Organization:
    org = Organization(github_id)

    settings = client.get_org_settings(github_id)
    org.update_settings(settings)

    webhooks = client.get_webhooks(github_id)
    org.update_webhooks(webhooks)

    repos = []
    repo_names = client.get_repos(github_id)
    for repo_name in repo_names:
        repo_data = client.get_repo_data(github_id, repo_name)
        rules = client.get_branch_protection_rules(github_id, repo_name)

        if len(rules) > 0:
            rule_list = []
            for rule in rules:
                rule_list.append(schemas.get_items_contained_in_schema(rule, schemas.BRANCH_PROTECTION_RULE_SCHEMA))

            repo_data["branch_protection_rules"] = rule_list

        repos.append(repo_data)

    org.update_repos(repos)

    org.validate()
    return org
