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
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from functools import partial
from io import StringIO
from typing import Any

import jsonschema
from importlib_resources import files, as_file

from . import mapping
from . import resources
from . import schemas
from . import utils
from .config import JsonnetConfig, OtterdogConfig
from .github import Github


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
        utils.print_debug("updating settings to " + json.dumps(data, indent=2))
        self._dict["settings"] = data

    def get_webhooks(self) -> list[dict[str, Any]]:
        return self._dict.get("webhooks", [])

    def update_webhooks(self, webhooks: list[dict[str, Any]]) -> None:
        utils.print_debug("updating webhooks to " + json.dumps(webhooks, indent=2))
        self._dict["webhooks"] = webhooks

    def get_repos(self) -> list[dict[str, Any]]:
        return self._dict.get("repositories", [])

    def update_repos(self, repos: list[dict[str, Any]]) -> None:
        utils.print_debug("updating repos to " + json.dumps(repos, indent=2))
        self._dict["repositories"] = repos

    def validate(self) -> None:
        self._validate_org_config(self._dict)

    @staticmethod
    def _validate_org_config(data: dict[str, Any]) -> None:
        with as_file(files(resources).joinpath("schemas")) as resource_dir:
            schema_root = resource_dir.as_uri()
            resolver = jsonschema.validators.RefResolver(base_uri=f"{schema_root}/", referrer=data)
            jsonschema.validate(instance=data, schema=schemas.ORG_SCHEMA, resolver=resolver)

    def write_jsonnet_config(self, config: JsonnetConfig) -> str:
        default_config = config.default_org_config

        output = StringIO()
        output.write(textwrap.dedent(f"""
            local orgs = {config.get_import_statement()};

            orgs.{config.create_org}('{self.github_id}') {{
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
                output.write(f"      orgs.{config.create_webhook}() ")
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

                output.write(f"      orgs.{config.create_repo}('{name}') ")

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
                        output.write(f"orgs.{config.create_branch_protection_rule}('{pattern}') ")
                        utils.dump_json_object(rule_diff, output, offset=o, indent=2, embedded_object=True)

                    o -= 2
                    output.write(" " * o)
                    output.write("],\n")

                utils.dump_json_object(diff_obj, output, offset=6, indent=2, embedded_object=True,
                                       predicate=is_branch_protection_rule_key,
                                       func=dump_branch_protection_rule)

            output.write("    ]\n")

        output.write("}")
        return output.getvalue()

    def __str__(self) -> str:
        return f"Organization(id={self.github_id})"


def load_from_file(github_id: str,
                   config_file: str,
                   config: OtterdogConfig,
                   resolve_secrets: bool = True) -> Organization:
    if not os.path.exists(config_file):
        msg = f"configuration file '{config_file}' for organization '{github_id}' does not exist"
        raise RuntimeError(msg)

    utils.print_debug(f"loading configuration for organization {github_id} from file {config_file}")
    org_data = utils.jsonnet_evaluate_file(config_file)

    # resolve webhook secrets
    if resolve_secrets:
        for webhook in org_data["webhooks"]:
            if "secret" in webhook:
                webhook["secret"] = config.get_secret(webhook["secret"])

    org = Organization(github_id)
    org.load_config(org_data)
    return org


def _process_single_repo(gh_client: Github, github_id: str, repo_name: str) -> (str, dict[str, Any]):
    github_repo_data = gh_client.get_repo_data(github_id, repo_name)
    otterdog_repo_data = mapping.map_github_repo_data_to_otterdog(github_repo_data)

    rules = gh_client.get_branch_protection_rules(github_id, repo_name)
    if len(rules) > 0:
        rule_list = []
        for rule in rules:
            rule_list.append(schemas.get_items_contained_in_schema(rule, schemas.BRANCH_PROTECTION_RULE_SCHEMA))

        otterdog_repo_data["branch_protection_rules"] = rule_list

    return repo_name, otterdog_repo_data


def load_from_github(github_id: str,
                     jsonnet_config: JsonnetConfig,
                     client: Github,
                     printer: utils.IndentingPrinter = None) -> Organization:

    org = Organization(github_id)

    default_settings = jsonnet_config.default_org_config["settings"]

    start = datetime.now()
    if printer is not None:
        printer.print(f"\norganization settings: Reading...")

    github_settings = client.get_org_settings(github_id, set(default_settings.keys()))
    otterdog_settings = mapping.map_github_org_settings_data_to_otterdog(github_settings)

    if printer is not None:
        end = datetime.now()
        printer.print(f"organization settings: Read complete after {(end - start).total_seconds()}s")

    org.update_settings(otterdog_settings)

    start = datetime.now()
    if printer is not None:
        printer.print(f"\nwebhooks: Reading...")

    webhooks = client.get_webhooks(github_id)

    if printer is not None:
        end = datetime.now()
        printer.print(f"webhooks: Read complete after {(end - start).total_seconds()}s")

    otterdog_webhooks = []
    for webhook in webhooks:
        otterdog_webhooks.append(mapping.map_github_org_webhook_data_to_otterdog(webhook))

    org.update_webhooks(otterdog_webhooks)

    start = datetime.now()
    if printer is not None:
        printer.print(f"\nrepositories: Reading...")

    repos = []
    repo_names = client.get_repos(github_id)

    # retrieve repo_data and branch_protection_rules in parallel using a pool.
    github_repos = {}
    # partially apply the github_client and the github_id to get a function that only takes one parameter
    process_repo = partial(_process_single_repo, client, github_id)
    # use a process pool executor: tests show that this is faster than a ThreadPoolExecutor
    # due to the global interpreter lock.
    with ProcessPoolExecutor() as pool:
        data = pool.map(process_repo, repo_names)
        for (repo_name, repo_data) in data:
            github_repos[repo_name] = repo_data

    if printer is not None:
        end = datetime.now()
        printer.print(f"repositories: Read complete after {(end - start).total_seconds()}s")

    for repo_name, repo_data in github_repos.items():
        repos.append(repo_data)

    org.update_repos(repos)
    org.validate()
    return org
