# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os
import textwrap
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from io import StringIO
from typing import Any

import jsonschema
from importlib_resources import files, as_file
from jsonbender import bend, S, F, Forall

from otterdog import resources
from otterdog import schemas
from otterdog import utils
from otterdog.config import OtterdogConfig, JsonnetConfig
from otterdog.providers.github import Github
from otterdog.utils import is_unset

from . import ValidationContext
from .branch_protection_rule import BranchProtectionRule
from .organization_settings import OrganizationSettings
from .organization_webhook import OrganizationWebhook
from .repository import Repository


@dataclass
class GitHubOrganization:
    github_id: str
    settings: OrganizationSettings
    webhooks: list[OrganizationWebhook] = field(default_factory=list)
    repositories: list[Repository] = field(default_factory=list)

    def add_webhook(self, webhook: OrganizationWebhook) -> None:
        self.webhooks.append(webhook)

    def set_webhooks(self, webhooks: list[OrganizationWebhook]) -> None:
        self.webhooks = webhooks

    def add_repository(self, repo: Repository) -> None:
        self.repositories.append(repo)

    def set_repositories(self, repos: list[Repository]) -> None:
        self.repositories = repos

    def validate(self) -> ValidationContext:
        context = ValidationContext()
        self.settings.validate(context, self)

        for webhook in self.webhooks:
            webhook.validate(context, self)

        for repo in self.repositories:
            repo.validate(context, self)

        return context

    @staticmethod
    def _validate_org_config(data: dict[str, Any]) -> None:
        with as_file(files(resources).joinpath("schemas")) as resource_dir:
            schema_root = resource_dir.as_uri()
            resolver = jsonschema.validators.RefResolver(base_uri=f"{schema_root}/", referrer=data)
            jsonschema.validate(instance=data, schema=schemas.ORG_SCHEMA, resolver=resolver)

    @classmethod
    def from_model(cls, data: dict[str, Any]) -> "GitHubOrganization":
        # validate the input data with the json schema.
        cls._validate_org_config(data)

        mapping = {
            "github_id": S("github_id"),
            "settings": S("settings") >> F(lambda x: OrganizationSettings.from_model(x)),
            "webhooks": S("webhooks") >> Forall(lambda x: OrganizationWebhook.from_model(x)),
            "repositories": S("repositories") >> Forall(lambda x: Repository.from_model(x))
        }

        return cls(**bend(mapping, data))

    def to_jsonnet(self, config: JsonnetConfig, ignored_keys: set[str]) -> str:
        default_org = GitHubOrganization.from_model(config.default_org_config)

        offset = 4
        indent = 2

        output = StringIO()
        output.write(textwrap.dedent(f"""
            local orgs = {config.get_import_statement()};

            orgs.{config.create_org}('{self.github_id}') {{
                settings+:"""))

        default_org_settings = default_org.settings
        settings_patch = self.settings.get_patch_to(default_org_settings)

        # some keys to be ignored, mainly for web settings when
        # specifying '--no-web-ui' flag.
        for ignored_key in ignored_keys:
            settings_patch.pop(ignored_key)

        utils.dump_patch_object_as_json(settings_patch, output, offset=offset, indent=indent)

        if len(self.webhooks) > 0:
            default_org_webhook = OrganizationWebhook.from_model(config.default_org_webhook_config)

            output.write(" " * offset + "webhooks+: [\n")
            offset += indent

            for webhook in self.webhooks:
                webhook_patch = webhook.get_patch_to(default_org_webhook)
                output.write(" " * offset + f"orgs.{config.create_webhook}()")
                utils.dump_patch_object_as_json(webhook_patch, output, offset=offset, indent=indent)

            offset -= indent
            output.write(" " * offset + "],\n")

        if len(self.repositories) > 0:
            repos_by_name = utils.associate_by_key(self.repositories, lambda x: x.name)
            default_repos_by_name = utils.associate_by_key(default_org.repositories, lambda x: x.name)

            # add all default repos which are not yet contained in repos
            for default_repo_name, default_repo in default_repos_by_name.items():
                if repos_by_name.get(default_repo_name) is None:
                    repos_by_name[default_repo_name] = default_repo

            default_org_repo = Repository.from_model(config.default_org_repo_config)

            output.write(" " * offset + "_repositories+:: [\n")
            offset += indent

            for repo_name, repo in sorted(repos_by_name.items()):
                if repo_name in default_repos_by_name:
                    other_repo = default_repos_by_name[repo_name]
                    function = f"orgs.{config.extend_repo}"
                    extend = True
                else:
                    other_repo = default_org_repo
                    function = f"orgs.{config.create_repo}"
                    extend = False

                repo_patch = repo.get_patch_to(other_repo)

                has_branch_protection_rules = len(repo.branch_protection_rules) > 0
                has_changes = len(repo_patch) > 0 or has_branch_protection_rules
                if extend and has_changes is False:
                    continue

                # remove the name key from the diff_obj to avoid serializing twice to json
                if "name" in repo_patch:
                    repo_patch.pop("name")

                output.write(" " * offset + f"{function}('{repo_name}')")

                offset = \
                    utils.dump_patch_object_as_json(repo_patch,
                                                    output,
                                                    offset=offset,
                                                    indent=indent,
                                                    close_object=False)

                if has_branch_protection_rules:
                    default_org_rule = BranchProtectionRule.from_model(config.default_org_branch_config)

                    output.write(" " * offset + "branch_protection_rules: [\n")
                    offset += indent

                    for rule in repo.branch_protection_rules:
                        rule_patch = rule.get_patch_to(default_org_rule)
                        rule_patch.pop("pattern")

                        output.write(" " * offset +
                                     f"orgs.{config.create_branch_protection_rule}('{rule.pattern}')")
                        utils.dump_patch_object_as_json(rule_patch, output, offset=offset, indent=indent)

                    offset -= indent
                    output.write(" " * offset + "],\n")

                # close the repo object
                offset -= indent
                output.write(" " * offset + "},\n")

            offset -= indent
            output.write(" " * offset + "],\n")

        output.write("}")
        return output.getvalue()


def load_github_organization_from_file(github_id: str,
                                       config_file: str,
                                       config: OtterdogConfig,
                                       resolve_secrets: bool = True) -> GitHubOrganization:
    if not os.path.exists(config_file):
        msg = f"configuration file '{config_file}' for organization '{github_id}' does not exist"
        raise RuntimeError(msg)

    utils.print_debug(f"loading configuration for organization {github_id} from file {config_file}")
    data = utils.jsonnet_evaluate_file(config_file)

    org = GitHubOrganization.from_model(data)

    # resolve webhook secrets
    if resolve_secrets:
        for webhook in org.webhooks:
            secret = webhook.secret
            if not is_unset(secret) and secret is not None:
                webhook.secret = config.get_secret(secret)

    return org


def _process_single_repo(gh_client: Github, github_id: str, repo_name: str) -> tuple[str, Repository]:
    # get repo data
    github_repo_data = gh_client.get_repo_data(github_id, repo_name)
    repo = Repository.from_provider(github_repo_data)

    # get branch protection rules of the repo
    rules = gh_client.get_branch_protection_rules(github_id, repo_name)
    for github_rule in rules:
        repo.add_branch_protection_rule(BranchProtectionRule.from_provider(github_rule))

    return repo_name, repo


def load_github_organization_from_provider(github_id: str,
                                           jsonnet_config: JsonnetConfig,
                                           client: Github,
                                           no_web_ui: bool = False,
                                           printer: utils.IndentingPrinter = None) -> GitHubOrganization:

    default_settings = jsonnet_config.default_org_config["settings"]

    start = datetime.now()
    if printer is not None:
        printer.print(f"\norganization settings: Reading...")

    included_keys = set(default_settings.keys())
    # if no_web_ui is set, filter out any web settings
    if no_web_ui is True:
        included_keys = {x for x in included_keys if not client.is_web_org_setting(x)}

    github_settings = client.get_org_settings(github_id, included_keys)

    if printer is not None:
        end = datetime.now()
        printer.print(f"organization settings: Read complete after {(end - start).total_seconds()}s")

    settings = OrganizationSettings.from_provider(github_settings)
    org = GitHubOrganization(github_id, settings)

    start = datetime.now()
    if printer is not None:
        printer.print(f"\nwebhooks: Reading...")

    github_webhooks = client.get_webhooks(github_id)

    if printer is not None:
        end = datetime.now()
        printer.print(f"webhooks: Read complete after {(end - start).total_seconds()}s")

    for webhook in github_webhooks:
        org.add_webhook(OrganizationWebhook.from_provider(webhook))

    start = datetime.now()
    if printer is not None:
        printer.print(f"\nrepositories: Reading...")

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

    for repo_name, repo in github_repos.items():
        org.add_repository(repo)

    return org
