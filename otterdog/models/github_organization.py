#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
from datetime import datetime
from io import StringIO
from typing import Any, Callable, Iterator, Optional

import jsonschema
from importlib_resources import as_file, files
from jsonbender import F, Forall, OptionalS, S, bend  # type: ignore

from otterdog import resources
from otterdog.config import JsonnetConfig, OtterdogConfig
from otterdog.models import (
    LivePatchContext,
    LivePatchHandler,
    ModelObject,
    PatchContext,
    ValidationContext,
)
from otterdog.models.branch_protection_rule import BranchProtectionRule
from otterdog.models.environment import Environment
from otterdog.models.organization_secret import OrganizationSecret
from otterdog.models.organization_settings import OrganizationSettings
from otterdog.models.organization_variable import OrganizationVariable
from otterdog.models.organization_webhook import OrganizationWebhook
from otterdog.models.organization_workflow_settings import OrganizationWorkflowSettings
from otterdog.models.repo_ruleset import RepositoryRuleset
from otterdog.models.repo_secret import RepositorySecret
from otterdog.models.repo_variable import RepositoryVariable
from otterdog.models.repo_webhook import RepositoryWebhook
from otterdog.models.repo_workflow_settings import RepositoryWorkflowSettings
from otterdog.models.repository import Repository
from otterdog.providers.github import GitHubProvider
from otterdog.utils import (
    IndentingPrinter,
    associate_by_key,
    is_debug_enabled,
    is_info_enabled,
    jsonnet_evaluate_file,
    print_debug,
)

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
    variables: list[OrganizationVariable] = dataclasses.field(default_factory=list)
    repositories: list[Repository] = dataclasses.field(default_factory=list)

    _secrets_resolved: bool = False

    @property
    def secrets_resolved(self) -> bool:
        return self._secrets_resolved

    def add_webhook(self, webhook: OrganizationWebhook) -> None:
        self.webhooks.append(webhook)

    def get_webhook(self, url: str) -> Optional[OrganizationWebhook]:
        return next(filter(lambda x: x.url == url, self.webhooks), None)  # type: ignore

    def set_webhooks(self, webhooks: list[OrganizationWebhook]) -> None:
        self.webhooks = webhooks

    def add_secret(self, secret: OrganizationSecret) -> None:
        self.secrets.append(secret)

    def get_secret(self, name: str) -> Optional[OrganizationSecret]:
        return next(filter(lambda x: x.name == name, self.secrets), None)  # type: ignore

    def set_secrets(self, secrets: list[OrganizationSecret]) -> None:
        self.secrets = secrets

    def add_variable(self, variable: OrganizationVariable) -> None:
        self.variables.append(variable)

    def get_variable(self, name: str) -> Optional[OrganizationVariable]:
        return next(filter(lambda x: x.name == name, self.variables), None)  # type: ignore

    def set_variables(self, variables: list[OrganizationVariable]) -> None:
        self.variables = variables

    def add_repository(self, repo: Repository) -> None:
        self.repositories.append(repo)

    def get_repository(self, repo_name: str) -> Optional[Repository]:
        return next(filter(lambda x: x.name == repo_name, self.repositories), None)  # type: ignore

    def set_repositories(self, repos: list[Repository]) -> None:
        self.repositories = repos

    def validate(self, template_dir: str) -> ValidationContext:
        context = ValidationContext(self, template_dir)
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

        for variable in self.variables:
            yield variable, None
            yield from variable.get_model_objects()

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
            "webhooks": OptionalS("webhooks", default=[]) >> Forall(lambda x: OrganizationWebhook.from_model_data(x)),
            "secrets": OptionalS("secrets", default=[]) >> Forall(lambda x: OrganizationSecret.from_model_data(x)),
            "variables": OptionalS("variables", default=[])
            >> Forall(lambda x: OrganizationVariable.from_model_data(x)),
            "repositories": OptionalS("repositories", default=[]) >> Forall(lambda x: Repository.from_model_data(x)),
        }

        return cls(**bend(mapping, data))

    def resolve_secrets(self, secret_resolver: Callable[[str], str]) -> None:
        for webhook in self.webhooks:
            webhook.resolve_secrets(secret_resolver)

        for secret in self.secrets:
            secret.resolve_secrets(secret_resolver)

        for repo in self.repositories:
            repo.resolve_secrets(secret_resolver)

        self._secrets_resolved = True

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

    def to_jsonnet(self, config: JsonnetConfig, context: PatchContext) -> str:
        default_org = GitHubOrganization.from_model_data(config.default_org_config_for_org_id(self.github_id))

        output = StringIO()
        printer = IndentingPrinter(output)

        printer.println(f"local orgs = {config.import_statement};")
        printer.println()
        printer.println(f"orgs.{config.create_org}('{self.github_id}') {{")
        printer.level_up()

        # print organization settings
        printer.print("settings+:")
        self.settings.to_jsonnet(printer, config, context, False, default_org.settings)

        # print organization webhooks
        if len(self.webhooks) > 0:
            default_org_webhook = OrganizationWebhook.from_model_data(config.default_org_webhook_config)

            printer.println("webhooks+: [")
            printer.level_up()

            for webhook in self.webhooks:
                webhook.to_jsonnet(printer, config, context, False, default_org_webhook)

            printer.level_down()
            printer.println("],")

        # print organization secrets
        if len(self.secrets) > 0:
            default_org_secret = OrganizationSecret.from_model_data(config.default_org_secret_config)

            printer.println("secrets+: [")
            printer.level_up()

            for secret in self.secrets:
                secret.to_jsonnet(printer, config, context, False, default_org_secret)

            printer.level_down()
            printer.println("],")

        # print organization variables
        if len(self.variables) > 0:
            default_org_variable = OrganizationVariable.from_model_data(config.default_org_variable_config)

            printer.println("variables+: [")
            printer.level_up()

            for variable in self.variables:
                variable.to_jsonnet(printer, config, context, False, default_org_variable)

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

                repo.to_jsonnet(printer, config, context, extend, other_repo)

            printer.level_down()
            printer.println("],")

        printer.level_down()
        printer.println("}")

        return output.getvalue()

    def generate_live_patch(
        self, current_organization: GitHubOrganization, context: LivePatchContext, handler: LivePatchHandler
    ) -> None:
        OrganizationSettings.generate_live_patch(self.settings, current_organization.settings, None, context, handler)

        OrganizationWebhook.generate_live_patch_of_list(
            self.webhooks,
            current_organization.webhooks,
            None,
            context,
            handler,
        )

        OrganizationSecret.generate_live_patch_of_list(
            self.secrets, current_organization.secrets, None, context, handler
        )

        OrganizationVariable.generate_live_patch_of_list(
            self.variables, current_organization.variables, None, context, handler
        )

        Repository.generate_live_patch_of_list(
            self.repositories, current_organization.repositories, None, context, handler
        )

    @classmethod
    def load_from_file(
        cls,
        github_id: str,
        config_file: str,
        config: OtterdogConfig,
        resolve_secrets: bool = False,
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
    async def load_from_provider(
        cls,
        github_id: str,
        jsonnet_config: JsonnetConfig,
        provider: GitHubProvider,
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
        github_settings = await provider.get_org_settings(github_id, included_keys, no_web_ui)

        if printer is not None and is_info_enabled():
            end = datetime.now()
            printer.println(f"organization settings: Read complete after {(end - start).total_seconds()}s")

        settings = OrganizationSettings.from_provider_data(github_id, github_settings)

        if "workflows" in included_keys:
            workflow_settings = await provider.get_org_workflow_settings(github_id)
            settings.workflows = OrganizationWorkflowSettings.from_provider_data(github_id, workflow_settings)

        org = cls(github_id, settings)

        if printer is not None and is_info_enabled():
            start = datetime.now()
            printer.println("\nwebhooks: Reading...")

        if jsonnet_config.default_org_webhook_config is not None:
            github_webhooks = await provider.get_org_webhooks(github_id)

            if printer is not None and is_info_enabled():
                end = datetime.now()
                printer.println(f"webhooks: Read complete after {(end - start).total_seconds()}s")

            for webhook in github_webhooks:
                org.add_webhook(OrganizationWebhook.from_provider_data(github_id, webhook))
        else:
            print_debug("not reading org webhooks, no default config available")

        if jsonnet_config.default_org_secret_config is not None:
            start = datetime.now()
            if printer is not None and is_info_enabled():
                printer.println("\nsecrets: Reading...")

            github_secrets = await provider.get_org_secrets(github_id)

            if printer is not None and is_info_enabled():
                end = datetime.now()
                printer.println(f"secrets: Read complete after {(end - start).total_seconds()}s")

            for secret in github_secrets:
                org.add_secret(OrganizationSecret.from_provider_data(github_id, secret))
        else:
            print_debug("not reading org secrets, no default config available")

        if jsonnet_config.default_org_variable_config is not None:
            start = datetime.now()
            if printer is not None and is_info_enabled():
                printer.println("\nvariables: Reading...")

            github_variables = await provider.get_org_variables(github_id)

            if printer is not None and is_info_enabled():
                end = datetime.now()
                printer.println(f"variables: Read complete after {(end - start).total_seconds()}s")

            for variable in github_variables:
                org.add_variable(OrganizationVariable.from_provider_data(github_id, variable))
        else:
            print_debug("not reading org secrets, no default config available")

        if jsonnet_config.default_repo_config is not None:
            for repo in await _load_repos_from_provider(github_id, provider, jsonnet_config, printer):
                org.add_repository(repo)
        else:
            print_debug("not reading repos, no default config available")

        return org


async def _process_single_repo(
    gh_client: GitHubProvider,
    github_id: str,
    repo_name: str,
    jsonnet_config: JsonnetConfig,
    teams: dict[str, Any],
    app_installations: dict[str, str],
) -> tuple[str, Repository]:
    rest_api = gh_client.rest_api

    # get repo data
    github_repo_data = await rest_api.repo.get_repo_data(github_id, repo_name)
    repo = Repository.from_provider_data(github_id, github_repo_data)

    github_repo_workflow_data = await rest_api.repo.get_workflow_settings(github_id, repo_name)
    repo.workflows = RepositoryWorkflowSettings.from_provider_data(github_id, github_repo_workflow_data)

    if jsonnet_config.default_branch_protection_rule_config is not None:
        # get branch protection rules of the repo
        rules = await gh_client.get_branch_protection_rules(github_id, repo_name)
        for github_rule in rules:
            repo.add_branch_protection_rule(BranchProtectionRule.from_provider_data(github_id, github_rule))
    else:
        print_debug("not reading branch protection rules, no default config available")

    # repository rulesets are not available for private repos and free plan
    # TODO: support rulesets in private repos with enterprise plan
    if jsonnet_config.default_repo_ruleset_config is not None and repo.private is False:
        # get rulesets of the repo
        rulesets = await rest_api.repo.get_rulesets(github_id, repo_name)
        for github_ruleset in rulesets:
            # FIXME: need to associate an app id to its slug
            #        GitHub does not support that atm, so we lookup the currently installed
            #        apps for an organization which provide a mapping from id to slug.
            for actor in github_ruleset.get("bypass_actors", []):
                if actor.get("actor_type", None) == "Integration":
                    actor_id = str(actor.get("actor_id", 0))
                    if actor_id in app_installations:
                        actor["app_slug"] = app_installations[actor_id]
                elif actor.get("actor_type", None) == "Team":
                    actor_id = str(actor.get("actor_id", 0))
                    if actor_id in teams:
                        actor["team_slug"] = teams[actor_id]

            for rule in github_ruleset.get("rules", []):
                if rule.get("type", None) == "required_status_checks":
                    required_status_checks = rule.get("parameters", {}).get("required_status_checks", [])
                    for status_check in required_status_checks:
                        integration_id = str(status_check.get("integration_id", 0))
                        if integration_id in app_installations:
                            status_check["app_slug"] = app_installations[integration_id]

            repo.add_ruleset(RepositoryRuleset.from_provider_data(github_id, github_ruleset))
    else:
        print_debug("not reading repo rulesets, no default config available")

    if jsonnet_config.default_org_webhook_config is not None:
        # get webhooks of the repo
        webhooks = await rest_api.repo.get_webhooks(github_id, repo_name)
        for github_webhook in webhooks:
            repo.add_webhook(RepositoryWebhook.from_provider_data(github_id, github_webhook))
    else:
        print_debug("not reading repo webhooks, no default config available")

    if jsonnet_config.default_repo_secret_config is not None:
        # get secrets of the repo
        secrets = await rest_api.repo.get_secrets(github_id, repo_name)
        for github_secret in secrets:
            repo.add_secret(RepositorySecret.from_provider_data(github_id, github_secret))
    else:
        print_debug("not reading repo secrets, no default config available")

    if jsonnet_config.default_repo_variable_config is not None:
        # get variables of the repo
        variables = await rest_api.repo.get_variables(github_id, repo_name)
        for github_variable in variables:
            repo.add_variable(RepositoryVariable.from_provider_data(github_id, github_variable))
    else:
        print_debug("not reading repo variables, no default config available")

    if jsonnet_config.default_environment_config is not None:
        # get environments of the repo
        environments = await rest_api.repo.get_environments(github_id, repo_name)
        for github_environment in environments:
            repo.add_environment(Environment.from_provider_data(github_id, github_environment))
    else:
        print_debug("not reading environments, no default config available")

    if is_debug_enabled():
        print_debug(f"done retrieving data for repo '{repo_name}'")

    return repo_name, repo


async def _load_repos_from_provider(
    github_id: str, provider: GitHubProvider, jsonnet_config: JsonnetConfig, printer: Optional[IndentingPrinter] = None
) -> list[Repository]:
    start = datetime.now()
    if printer is not None and is_info_enabled():
        printer.println("\nrepositories: Reading...")

    repo_names = await provider.get_repos(github_id)

    teams = {
        str(team["id"]): f"{github_id}/{team['slug']}" for team in await provider.rest_api.org.get_teams(github_id)
    }

    app_installations = {
        str(installation["app_id"]): installation["app_slug"]
        for installation in await provider.rest_api.org.get_app_installations(github_id)
    }

    result = await asyncio.gather(
        *[
            _process_single_repo(provider, github_id, repo_name, jsonnet_config, teams, app_installations)
            for repo_name in repo_names
        ]
    )

    github_repos = []
    for data in result:
        _, repo_data = data
        github_repos.append(repo_data)

    if printer is not None and is_info_enabled():
        end = datetime.now()
        printer.println(f"repositories: Read complete after {(end - start).total_seconds()}s")

    return github_repos
