# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

import dataclasses
import json
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from functools import partial
from io import StringIO
from typing import Any, Optional, Iterator, Callable

import jsonschema
from importlib_resources import files, as_file
from jsonbender import bend, S, F, Forall  # type: ignore

from otterdog import resources
from otterdog.config import OtterdogConfig, JsonnetConfig
from otterdog.providers.github import Github
from otterdog.utils import (
    IndentingPrinter,
    associate_by_key,
    print_debug,
    jsonnet_evaluate_file,
    is_info_enabled,
)

from . import ValidationContext, ModelObject
from .branch_protection_rule import BranchProtectionRule
from .environment import Environment
from .organization_secret import OrganizationSecret
from .organization_settings import OrganizationSettings
from .organization_webhook import OrganizationWebhook
from .repository import Repository
from .repo_secret import RepositorySecret
from .repo_webhook import RepositoryWebhook

_ORG_SCHEMA = json.loads(files(resources).joinpath("schemas/organization.json").read_text())


@dataclasses.dataclass
class GitHubOrganization:
    """
    Represents a GitHub Organization with its associated resources.
    """

    github_id: str
    settings: OrganizationSettings
    webhooks: list[OrganizationWebhook] = dataclasses.field(default_factory=list)
    secrets: list[OrganizationSecret] = dataclasses.field(default_factory=list)
    repositories: list[Repository] = dataclasses.field(default_factory=list)

    def add_webhook(self, webhook: OrganizationWebhook) -> None:
        self.webhooks.append(webhook)

    def get_webhook(self, url: str) -> Optional[OrganizationWebhook]:
        for webhook in self.webhooks:
            if webhook.url == url:
                return webhook

        return None

    def set_webhooks(self, webhooks: list[OrganizationWebhook]) -> None:
        self.webhooks = webhooks

    def add_secret(self, secret: OrganizationSecret) -> None:
        self.secrets.append(secret)

    def get_secret(self, name: str) -> Optional[OrganizationSecret]:
        for secret in self.secrets:
            if secret.name == name:
                return secret

        return None

    def set_secrets(self, secrets: list[OrganizationSecret]) -> None:
        self.secrets = secrets

    def add_repository(self, repo: Repository) -> None:
        self.repositories.append(repo)

    def get_repository(self, repo_name: str) -> Optional[Repository]:
        for repo in self.repositories:
            if repo.name == repo_name:
                return repo

        return None

    def set_repositories(self, repos: list[Repository]) -> None:
        self.repositories = repos

    def validate(self, template_dir: str) -> ValidationContext:
        context = ValidationContext(template_dir)
        self.settings.validate(context, self)

        for webhook in self.webhooks:
            webhook.validate(context, self)

        for secret in self.secrets:
            secret.validate(context, self)

        for repo in self.repositories:
            repo.validate(context, self)

        return context

    @staticmethod
    def _validate_org_config(data: dict[str, Any]) -> None:
        with as_file(files(resources).joinpath("schemas")) as resource_dir:
            schema_root = resource_dir.as_uri()
            resolver = jsonschema.validators.RefResolver(base_uri=f"{schema_root}/", referrer=data)
            jsonschema.validate(instance=data, schema=_ORG_SCHEMA, resolver=resolver)

    def get_model_objects(self) -> Iterator[tuple[ModelObject, Optional[ModelObject]]]:
        yield self.settings, None
        yield from self.settings.get_model_objects()

        for webhook in self.webhooks:
            yield webhook, None
            yield from webhook.get_model_objects()

        for secret in self.secrets:
            yield secret, None
            yield from secret.get_model_objects()

        for repo in self.repositories:
            yield repo, None
            yield from repo.get_model_objects()

    @classmethod
    def from_model_data(cls, data: dict[str, Any]) -> GitHubOrganization:
        # validate the input data with the json schema.
        cls._validate_org_config(data)

        mapping = {
            "github_id": S("github_id"),
            "settings": S("settings") >> F(lambda x: OrganizationSettings.from_model_data(x)),
            "webhooks": S("webhooks") >> Forall(lambda x: OrganizationWebhook.from_model_data(x)),
            "secrets": S("secrets") >> Forall(lambda x: OrganizationSecret.from_model_data(x)),
            "repositories": S("repositories") >> Forall(lambda x: Repository.from_model_data(x)),
        }

        return cls(**bend(mapping, data))

    def resolve_secrets(self, secret_resolver: Callable[[str], str]) -> None:
        for webhook in self.webhooks:
            webhook.resolve_secrets(secret_resolver)

        for secret in self.secrets:
            secret.resolve_secrets(secret_resolver)

        for repo in self.repositories:
            repo.resolve_secrets(secret_resolver)

    def copy_secrets(self, other_org: GitHubOrganization) -> None:
        for webhook in self.webhooks:
            other_webhook = other_org.get_webhook(webhook.url)
            if other_webhook is not None:
                webhook.copy_secrets(other_webhook)

        for secret in self.secrets:
            other_secret = other_org.get_secret(secret.name)
            if other_secret is not None:
                secret.copy_secrets(other_secret)

        for repo in self.repositories:
            other_repo = other_org.get_repository(repo.name)
            if other_repo is not None:
                repo.copy_secrets(other_repo)

    def to_jsonnet(self, config: JsonnetConfig) -> str:
        default_org = GitHubOrganization.from_model_data(config.default_org_config)

        output = StringIO()
        printer = IndentingPrinter(output)

        printer.println(f"local orgs = {config.import_statement};")
        printer.println()
        printer.println(f"orgs.{config.create_org}('{self.github_id}') {{")
        printer.level_up()

        # print organization settings
        printer.print("settings+:")
        self.settings.to_jsonnet(printer, config, False, default_org.settings)

        # print organization webhooks
        if len(self.webhooks) > 0:
            default_org_webhook = OrganizationWebhook.from_model_data(config.default_org_webhook_config)

            printer.println("webhooks+: [")
            printer.level_up()

            for webhook in self.webhooks:
                webhook.to_jsonnet(printer, config, False, default_org_webhook)

            printer.level_down()
            printer.println("],")

        # print organization secrets
        if len(self.secrets) > 0:
            default_org_secret = OrganizationSecret.from_model_data(config.default_org_secret_config)

            printer.println("secrets+: [")
            printer.level_up()

            for secret in self.secrets:
                secret.to_jsonnet(printer, config, False, default_org_secret)

            printer.level_down()
            printer.println("],")

        # print repositories
        if len(self.repositories) > 0:
            repos_by_name = associate_by_key(self.repositories, lambda x: x.name)
            default_repos_by_name = associate_by_key(default_org.repositories, lambda x: x.name)

            # add all default repos which are not yet contained in repos
            for default_repo_name, default_repo in default_repos_by_name.items():
                if repos_by_name.get(default_repo_name) is None:
                    repos_by_name[default_repo_name] = default_repo

            default_org_repo = Repository.from_model_data(config.default_repo_config)

            printer.println("_repositories+:: [")
            printer.level_up()

            for repo_name, repo in sorted(repos_by_name.items()):
                if repo_name in default_repos_by_name:
                    other_repo = default_repos_by_name[repo_name]
                    extend = True
                else:
                    other_repo = default_org_repo
                    extend = False

                repo.to_jsonnet(printer, config, extend, other_repo)

            printer.level_down()
            printer.println("],")

        printer.level_down()
        printer.println("}")

        return output.getvalue()

    @classmethod
    def load_from_file(
        cls,
        github_id: str,
        config_file: str,
        config: OtterdogConfig,
        resolve_secrets: bool = True,
    ) -> GitHubOrganization:
        if not os.path.exists(config_file):
            msg = f"configuration file '{config_file}' for organization '{github_id}' does not exist"
            raise RuntimeError(msg)

        print_debug(f"loading configuration for organization {github_id} from file {config_file}")
        data = jsonnet_evaluate_file(config_file)

        org = cls.from_model_data(data)

        if resolve_secrets:
            org.resolve_secrets(config.get_secret)

        return org

    @classmethod
    def load_from_provider(
        cls,
        github_id: str,
        jsonnet_config: JsonnetConfig,
        client: Github,
        no_web_ui: bool = False,
        printer: Optional[IndentingPrinter] = None,
    ) -> GitHubOrganization:
        start = datetime.now()
        if printer is not None and is_info_enabled():
            printer.println("\norganization settings: Reading...")

        # FIXME: this uses the keys from the model schema which might be different to the provider schema
        #        for now this is the same for organization settings, but there might be cases where it is different.
        default_settings = jsonnet_config.default_org_config["settings"]
        included_keys = set(default_settings.keys())
        github_settings = client.get_org_settings(github_id, included_keys, no_web_ui)

        if printer is not None and is_info_enabled():
            end = datetime.now()
            printer.println(f"organization settings: Read complete after {(end - start).total_seconds()}s")

        settings = OrganizationSettings.from_provider_data(github_id, github_settings)
        org = cls(github_id, settings)

        start = datetime.now()
        if printer is not None and is_info_enabled():
            printer.println("\nwebhooks: Reading...")

        github_webhooks = client.get_org_webhooks(github_id)

        if printer is not None and is_info_enabled():
            end = datetime.now()
            printer.println(f"webhooks: Read complete after {(end - start).total_seconds()}s")

        for webhook in github_webhooks:
            org.add_webhook(OrganizationWebhook.from_provider_data(github_id, webhook))

        start = datetime.now()
        if printer is not None and is_info_enabled():
            printer.println("\nsecrets: Reading...")

        github_secrets = client.get_org_secrets(github_id)

        if printer is not None and is_info_enabled():
            end = datetime.now()
            printer.println(f"secrets: Read complete after {(end - start).total_seconds()}s")

        for secret in github_secrets:
            org.add_secret(OrganizationSecret.from_provider_data(github_id, secret))

        for repo in _load_repos_from_provider(github_id, client, printer):
            org.add_repository(repo)

        return org


def _process_single_repo(gh_client: Github, github_id: str, repo_name: str) -> tuple[str, Repository]:
    # get repo data
    github_repo_data = gh_client.get_repo_data(github_id, repo_name)
    repo = Repository.from_provider_data(github_id, github_repo_data)

    # get branch protection rules of the repo
    rules = gh_client.get_branch_protection_rules(github_id, repo_name)
    for github_rule in rules:
        repo.add_branch_protection_rule(BranchProtectionRule.from_provider_data(github_id, github_rule))

    # get webhooks of the repo
    webhooks = gh_client.get_repo_webhooks(github_id, repo_name)
    for github_webhook in webhooks:
        repo.add_webhook(RepositoryWebhook.from_provider_data(github_id, github_webhook))

    # get secrets of the repo
    secrets = gh_client.get_repo_secrets(github_id, repo_name)
    for github_secret in secrets:
        repo.add_secret(RepositorySecret.from_provider_data(github_id, github_secret))

    # get environments of the repo
    environments = gh_client.get_repo_environments(github_id, repo_name)
    for github_environment in environments:
        repo.add_environment(Environment.from_provider_data(github_id, github_environment))

    return repo_name, repo


def _load_repos_from_provider(
    github_id: str, client: Github, printer: Optional[IndentingPrinter] = None
) -> list[Repository]:
    start = datetime.now()
    if printer is not None and is_info_enabled():
        printer.println("\nrepositories: Reading...")

    repo_names = client.get_repos(github_id)

    # retrieve repo_data and branch_protection_rules in parallel using a pool.
    github_repos = []
    # partially apply the github_client and the github_id to get a function that only takes one parameter
    process_repo = partial(_process_single_repo, client, github_id)
    # use a process pool executor: tests show that this is faster than a ThreadPoolExecutor
    # due to the global interpreter lock.
    with ProcessPoolExecutor() as pool:
        data = pool.map(process_repo, repo_names)
        for _, repo_data in data:
            github_repos.append(repo_data)

    if printer is not None and is_info_enabled():
        end = datetime.now()
        printer.println(f"repositories: Read complete after {(end - start).total_seconds()}s")

    return github_repos
