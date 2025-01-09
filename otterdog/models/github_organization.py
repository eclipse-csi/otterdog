#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
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
from io import StringIO
from typing import TYPE_CHECKING, Any

from importlib_resources import as_file, files
from jsonbender import F, Forall, OptionalS, S, bend  # type: ignore

from otterdog import resources
from otterdog.logging import get_logger
from otterdog.models import (
    FailureType,
    LivePatchContext,
    LivePatchHandler,
    ModelObject,
    PatchContext,
    ValidationContext,
)
from otterdog.models.branch_protection_rule import BranchProtectionRule
from otterdog.models.custom_property import CustomProperty
from otterdog.models.environment import Environment
from otterdog.models.organization_role import OrganizationRole
from otterdog.models.organization_ruleset import OrganizationRuleset
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
from otterdog.models.team import Team
from otterdog.utils import IndentingPrinter, associate_by_key, debug_times, jsonnet_evaluate_file

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator
    from re import Pattern

    from otterdog.config import JsonnetConfig, OtterdogConfig, SecretResolver
    from otterdog.providers.github import GitHubProvider

_ORG_SCHEMA = json.loads(files(resources).joinpath("schemas/organization.json").read_text())

_logger = get_logger(__name__)


@dataclasses.dataclass
class GitHubOrganization:
    """
    Represents a GitHub Organization with its associated resources.
    """

    project_name: str
    github_id: str
    settings: OrganizationSettings
    roles: list[OrganizationRole] = dataclasses.field(default_factory=list)
    teams: list[Team] = dataclasses.field(default_factory=list)
    webhooks: list[OrganizationWebhook] = dataclasses.field(default_factory=list)
    secrets: list[OrganizationSecret] = dataclasses.field(default_factory=list)
    variables: list[OrganizationVariable] = dataclasses.field(default_factory=list)
    rulesets: list[OrganizationRuleset] = dataclasses.field(default_factory=list)
    repositories: list[Repository] = dataclasses.field(default_factory=list)

    _secrets_resolved: bool = False

    @property
    def secrets_resolved(self) -> bool:
        return self._secrets_resolved

    def add_role(self, role: OrganizationRole) -> None:
        self.roles.append(role)

    def get_role(self, name: str) -> OrganizationRole | None:
        return next(filter(lambda x: x.name == name, self.roles), None)  # type: ignore

    def set_roles(self, roles: list[OrganizationRole]) -> None:
        self.roles = roles

    def add_team(self, team: Team) -> None:
        self.teams.append(team)

    def get_team(self, name: str) -> Team | None:
        return next(filter(lambda x: x.name == name, self.teams), None)  # type: ignore

    def set_teams(self, teams: list[Team]) -> None:
        self.teams = teams

    def add_webhook(self, webhook: OrganizationWebhook) -> None:
        self.webhooks.append(webhook)

    def get_webhook(self, url: str) -> OrganizationWebhook | None:
        return next(filter(lambda x: x.url == url, self.webhooks), None)  # type: ignore

    def set_webhooks(self, webhooks: list[OrganizationWebhook]) -> None:
        self.webhooks = webhooks

    def add_secret(self, secret: OrganizationSecret) -> None:
        self.secrets.append(secret)

    def get_secret(self, name: str) -> OrganizationSecret | None:
        return next(filter(lambda x: x.name == name, self.secrets), None)  # type: ignore

    def set_secrets(self, secrets: list[OrganizationSecret]) -> None:
        self.secrets = secrets

    def add_variable(self, variable: OrganizationVariable) -> None:
        self.variables.append(variable)

    def get_variable(self, name: str) -> OrganizationVariable | None:
        return next(filter(lambda x: x.name == name, self.variables), None)  # type: ignore

    def set_variables(self, variables: list[OrganizationVariable]) -> None:
        self.variables = variables

    def add_ruleset(self, ruleset: OrganizationRuleset) -> None:
        self.rulesets.append(ruleset)

    def get_ruleset(self, name: str) -> OrganizationRuleset | None:
        return next(filter(lambda x: x.name == name, self.rulesets), None)  # type: ignore

    def set_rulesets(self, rulesets: list[OrganizationRuleset]) -> None:
        self.rulesets = rulesets

    def add_repository(self, repo: Repository) -> None:
        self.repositories.append(repo)

    def get_repository(self, repo_name: str) -> Repository | None:
        return next(filter(lambda x: x.name == repo_name, self.repositories), None)  # type: ignore

    def set_repositories(self, repos: list[Repository]) -> None:
        self.repositories = repos

    async def validate(
        self,
        config: OtterdogConfig,
        jsonnet_config: JsonnetConfig,
        secret_resolver: SecretResolver,
        provider: GitHubProvider,
    ) -> ValidationContext:
        # only retrieve the list of current organization members if there are teams defined
        if len(self.teams) > 0:
            org_members = {x["login"] for x in await provider.rest_api.org.list_members(self.github_id)}
        else:
            org_members = set()

        default_org = GitHubOrganization.from_model_data(
            jsonnet_config.default_org_config_for_org_id(self.project_name, self.github_id)
        )

        context = ValidationContext(
            self,
            secret_resolver,
            jsonnet_config.template_dir,
            org_members,
            {t.name for t in default_org.teams},
            config.exclude_teams_pattern,
        )
        self.settings.validate(context, self)

        enterprise_plan = self.settings.plan == "enterprise"

        if len(self.roles) > 0 and not enterprise_plan:
            context.add_failure(
                FailureType.ERROR,
                f"use of organization roles requires an 'enterprise' plan, while this organization is "
                f"currently on a '{self.settings.plan}' plan.",
            )
        else:
            for role in self.roles:
                role.validate(context, self)

        for team in self.teams:
            team.validate(context, self)

        for webhook in self.webhooks:
            webhook.validate(context, self)

        for secret in self.secrets:
            secret.validate(context, self)

        if len(self.rulesets) > 0 and not enterprise_plan:
            context.add_failure(
                FailureType.ERROR,
                f"use of organization rulesets requires an 'enterprise' plan, while this organization is "
                f"currently on a '{self.settings.plan}' plan.",
            )
        else:
            for ruleset in self.rulesets:
                ruleset.validate(context, self)

        for repo in self.repositories:
            repo.validate(context, self)

        return context

    @staticmethod
    def _validate_org_config(data: dict[str, Any]) -> None:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
        from referencing.exceptions import NoSuchResource

        with as_file(files(resources).joinpath("schemas")) as resource_dir:

            def retrieve_from_filesystem(uri: str):
                path = resource_dir.joinpath(uri)
                if not path.exists():
                    raise NoSuchResource(ref=uri)  # type: ignore

                contents = json.loads(path.read_text())
                return Resource.from_contents(contents)

            registry = Registry(retrieve=retrieve_from_filesystem)  # type: ignore
            validator = Draft202012Validator(_ORG_SCHEMA, registry=registry)
            validator.validate(data)

    def get_model_objects(self) -> Iterator[tuple[ModelObject, ModelObject | None]]:
        yield self.settings, None
        yield from self.settings.get_model_objects()

        for role in self.roles:
            yield role, None
            yield from role.get_model_objects()

        for team in self.teams:
            yield team, None
            yield from team.get_model_objects()

        for webhook in self.webhooks:
            yield webhook, None
            yield from webhook.get_model_objects()

        for secret in self.secrets:
            yield secret, None
            yield from secret.get_model_objects()

        for variable in self.variables:
            yield variable, None
            yield from variable.get_model_objects()

        for ruleset in self.rulesets:
            yield ruleset, None
            yield from ruleset.get_model_objects()

        for repo in self.repositories:
            yield repo, None
            yield from repo.get_model_objects()

    @classmethod
    def from_model_data(cls, data: dict[str, Any]) -> GitHubOrganization:
        # validate the input data with the json schema.
        cls._validate_org_config(data)

        mapping = {
            "project_name": S("project_name"),
            "github_id": S("github_id"),
            "settings": S("settings") >> F(lambda x: OrganizationSettings.from_model_data(x)),
            "roles": OptionalS("roles", default=[]) >> Forall(lambda x: OrganizationRole.from_model_data(x)),
            "teams": OptionalS("teams", default=[]) >> Forall(lambda x: Team.from_model_data(x)),
            "webhooks": OptionalS("webhooks", default=[]) >> Forall(lambda x: OrganizationWebhook.from_model_data(x)),
            "secrets": OptionalS("secrets", default=[]) >> Forall(lambda x: OrganizationSecret.from_model_data(x)),
            "variables": OptionalS("variables", default=[])
            >> Forall(lambda x: OrganizationVariable.from_model_data(x)),
            "rulesets": OptionalS("rulesets", default=[]) >> Forall(lambda x: OrganizationRuleset.from_model_data(x)),
            "repositories": OptionalS("repositories", default=[]) >> Forall(lambda x: Repository.from_model_data(x)),
        }

        org = cls(**bend(mapping, data))
        org.repositories = [x.coerce_from_org_settings(org.settings) for x in org.repositories]
        return org

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

    def update_dummy_secrets(self, new_value: str) -> None:
        for model_object, _ in self.get_model_objects():
            model_object.update_dummy_secrets(new_value)

    def unset_settings_requiring_web_ui(self) -> None:
        for model_object, _ in self.get_model_objects():
            model_object.unset_settings_requiring_web_ui()

    def to_jsonnet(self, config: JsonnetConfig, context: PatchContext) -> str:
        default_org = GitHubOrganization.from_model_data(
            config.default_org_config_for_org_id(self.project_name, self.github_id)
        )

        output = StringIO()
        printer = IndentingPrinter(output)

        printer.println(f"local orgs = {config.import_statement};")
        printer.println()
        printer.println(f"orgs.{config.create_org}('{self.project_name}', '{self.github_id}') {{")
        printer.level_up()

        # print organization settings
        printer.print("settings+:")
        self.settings.to_jsonnet(printer, config, context, False, default_org.settings)

        # print organization roles
        if len(self.roles) > 0:
            default_org_role = OrganizationRole.from_model_data(config.default_org_role_config)

            printer.println("roles+: [")
            printer.level_up()

            for role in self.roles:
                role.to_jsonnet(printer, config, context, False, default_org_role)

            printer.level_down()
            printer.println("],")

        # print teams
        if len(self.teams) > 0:
            teams_by_name = associate_by_key(self.teams, lambda x: x.name)
            default_teams_by_name = associate_by_key(default_org.teams, lambda x: x.name)

            # remove teams inherited from the default config
            for default_team_name in set(default_teams_by_name):
                if default_team_name in teams_by_name:
                    teams_by_name.pop(default_team_name)

            if len(teams_by_name) > 0:
                default_team = Team.from_model_data(config.default_team_config)

                printer.println("teams+: [")
                printer.level_up()

                for _, team in sorted(teams_by_name.items()):
                    team.to_jsonnet(printer, config, context, False, default_team)

                printer.level_down()
                printer.println("],")

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

        # print organization rulesets
        if len(self.rulesets) > 0:
            default_org_ruleset = OrganizationRuleset.from_model_data(config.default_org_ruleset_config)

            printer.println("rulesets+: [")
            printer.level_up()

            for ruleset in self.rulesets:
                ruleset.to_jsonnet(printer, config, context, False, default_org_ruleset)

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
        OrganizationRole.generate_live_patch_of_list(self.roles, current_organization.roles, None, context, handler)
        Team.generate_live_patch_of_list(self.teams, current_organization.teams, None, context, handler)
        OrganizationSettings.generate_live_patch(self.settings, current_organization.settings, None, context, handler)
        OrganizationWebhook.generate_live_patch_of_list(
            self.webhooks, current_organization.webhooks, None, context, handler
        )
        OrganizationSecret.generate_live_patch_of_list(
            self.secrets, current_organization.secrets, None, context, handler
        )
        OrganizationVariable.generate_live_patch_of_list(
            self.variables, current_organization.variables, None, context, handler
        )
        OrganizationRuleset.generate_live_patch_of_list(
            self.rulesets, current_organization.rulesets, None, context, handler
        )
        Repository.generate_live_patch_of_list(
            self.repositories, current_organization.repositories, None, context, handler
        )

    @classmethod
    def load_from_file(cls, github_id: str, config_file: str) -> GitHubOrganization:
        if not os.path.exists(config_file):
            msg = f"configuration file '{config_file}' for organization '{github_id}' does not exist"
            raise RuntimeError(msg)

        _logger.debug("loading configuration for organization '%s' from file '%s'", github_id, config_file)
        data = jsonnet_evaluate_file(config_file)

        return cls.from_model_data(data)

    @classmethod
    async def load_from_provider(
        cls,
        project_name: str,
        github_id: str,
        jsonnet_config: JsonnetConfig,
        provider: GitHubProvider,
        no_web_ui: bool = False,
        concurrency: int | None = None,
        repo_filter: str | None = None,
        exclude_teams: Pattern | None = None,
    ) -> GitHubOrganization:
        import asyncer

        @debug_times("settings")
        async def _load_settings() -> OrganizationSettings:
            # FIXME: this uses the keys from the model schema which might be different to the provider schema
            #        for now this is the same for organization settings, but there might be cases where it is different.
            default_settings = jsonnet_config.default_org_config["settings"]
            included_keys = set(default_settings.keys())
            github_settings = await provider.get_org_settings(github_id, included_keys, no_web_ui)

            if "workflows" in included_keys:
                github_settings["workflows"] = await provider.get_org_workflow_settings(github_id)

            settings = OrganizationSettings.from_provider_data(github_id, github_settings)

            if "workflows" in included_keys:
                github_org_workflow_data = await provider.get_org_workflow_settings(github_id)
                settings.workflows = OrganizationWorkflowSettings.from_provider_data(
                    github_id, github_org_workflow_data
                )

            if "custom_properties" in included_keys:
                github_custom_properties = await provider.get_org_custom_properties(github_id)
                settings.custom_properties = [
                    CustomProperty.from_provider_data(github_id, x) for x in github_custom_properties
                ]

            return settings

        org_settings = await _load_settings()
        org = cls(project_name, github_id, org_settings)

        @debug_times("roles")
        async def _load_roles() -> None:
            if jsonnet_config.default_org_role_config is not None and org.settings.plan == "enterprise":
                github_roles = await provider.get_org_custom_roles(github_id)
                for role in github_roles:
                    org.add_role(OrganizationRole.from_provider_data(github_id, role))
            else:
                _logger.debug("not reading org webhooks, no default config available")

        @debug_times("teams")
        async def _load_teams() -> None:
            if jsonnet_config.default_team_config is not None:
                default_org = GitHubOrganization.from_model_data(
                    jsonnet_config.default_org_config_for_org_id(project_name, github_id)
                )

                github_teams = await provider.get_org_teams(github_id)
                for team in github_teams:
                    team_name = team["name"]
                    team_slug = team["slug"]

                    default_org.get_team(team_name)
                    if (
                        exclude_teams is not None
                        and exclude_teams.match(team_slug)
                        and default_org.get_team(team_name) is None
                    ):
                        continue
                    team_members = await provider.get_org_team_members(github_id, team_slug)
                    team["members"] = team_members
                    org.add_team(Team.from_provider_data(github_id, team))
            else:
                _logger.debug("not reading teams, no default config available")

        @debug_times("webhooks")
        async def _load_webhooks() -> None:
            if jsonnet_config.default_org_webhook_config is not None:
                github_webhooks = await provider.get_org_webhooks(github_id)
                for webhook in github_webhooks:
                    org.add_webhook(OrganizationWebhook.from_provider_data(github_id, webhook))
            else:
                _logger.debug("not reading org webhooks, no default config available")

        @debug_times("secrets")
        async def _load_secrets() -> None:
            if jsonnet_config.default_org_secret_config is not None:
                github_secrets = await provider.get_org_secrets(github_id)
                for secret in github_secrets:
                    org.add_secret(OrganizationSecret.from_provider_data(github_id, secret))
            else:
                _logger.debug("not reading org secrets, no default config available")

        @debug_times("variables")
        async def _load_variables() -> None:
            if jsonnet_config.default_org_variable_config is not None:
                github_variables = await provider.get_org_variables(github_id)
                for variable in github_variables:
                    org.add_variable(OrganizationVariable.from_provider_data(github_id, variable))
            else:
                _logger.debug("not reading org secrets, no default config available")

        @debug_times("rulesets")
        async def _load_rulesets() -> None:
            if jsonnet_config.default_org_ruleset_config is not None and org.settings.plan == "enterprise":
                github_rulesets = await provider.get_org_rulesets(github_id)
                for ruleset in github_rulesets:
                    org.add_ruleset(OrganizationRuleset.from_provider_data(github_id, ruleset))
            else:
                _logger.debug("not reading org secrets, no default config available")

        @debug_times("repos")
        async def _load_repos() -> None:
            if jsonnet_config.default_repo_config is not None:
                async for repo in _load_repos_from_provider(
                    github_id,
                    org.settings,
                    provider,
                    jsonnet_config,
                    concurrency,
                    repo_filter,
                ):
                    org.add_repository(repo)
            else:
                _logger.debug("not reading repos, no default config available")

        async with asyncer.create_task_group() as task_group:
            task_group.soonify(_load_roles)()
            task_group.soonify(_load_teams)()
            task_group.soonify(_load_webhooks)()
            task_group.soonify(_load_secrets)()
            task_group.soonify(_load_variables)()
            task_group.soonify(_load_rulesets)()
            task_group.soonify(_load_repos)()

        return org


async def _process_single_repo(
    gh_client: GitHubProvider,
    github_id: str,
    org_settings: OrganizationSettings,
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
        _logger.debug("not reading branch protection rules, no default config available")

    if jsonnet_config.default_repo_ruleset_config is not None and (
        repo.private is False or org_settings.plan == "enterprise"
    ):
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
        _logger.debug("not reading repo rulesets, no default config available")

    if jsonnet_config.default_org_webhook_config is not None:
        # get webhooks of the repo
        webhooks = await rest_api.repo.get_webhooks(github_id, repo_name)
        for github_webhook in webhooks:
            repo.add_webhook(RepositoryWebhook.from_provider_data(github_id, github_webhook))
    else:
        _logger.debug("not reading repo webhooks, no default config available")

    if jsonnet_config.default_repo_secret_config is not None:
        # get secrets of the repo
        secrets = await rest_api.repo.get_secrets(github_id, repo_name)
        for github_secret in secrets:
            repo.add_secret(RepositorySecret.from_provider_data(github_id, github_secret))
    else:
        _logger.debug("not reading repo secrets, no default config available")

    if jsonnet_config.default_repo_variable_config is not None:
        # get variables of the repo
        variables = await rest_api.repo.get_variables(github_id, repo_name)
        for github_variable in variables:
            repo.add_variable(RepositoryVariable.from_provider_data(github_id, github_variable))
    else:
        _logger.debug("not reading repo variables, no default config available")

    if jsonnet_config.default_environment_config is not None:
        # get environments of the repo
        environments = await rest_api.repo.get_environments(github_id, repo_name)
        for github_environment in environments:
            repo.add_environment(Environment.from_provider_data(github_id, github_environment))
    else:
        _logger.debug("not reading environments, no default config available")

    _logger.debug("done retrieving data for repo '%s'", repo_name)

    return repo_name, repo


async def _load_repos_from_provider(
    github_id: str,
    org_settings: OrganizationSettings,
    provider: GitHubProvider,
    jsonnet_config: JsonnetConfig,
    concurrency: int | None = None,
    repo_filter: str | None = None,
) -> AsyncIterator[Repository]:
    import fnmatch

    repo_names = await provider.get_repos(github_id)

    if repo_filter is not None:
        repo_names = fnmatch.filter(repo_names, repo_filter)

    teams = {str(team["id"]): f"{github_id}/{team['slug']}" for team in await provider.get_org_teams(github_id)}

    app_installations = {
        str(installation["app_id"]): installation["app_slug"]
        for installation in await provider.rest_api.org.get_app_installations(github_id)
    }

    # limit the number of repos that are processed concurrently to avoid hitting secondary rate limits
    sem = asyncio.Semaphore(50 if concurrency is None else concurrency)

    async def safe_process(repo_name):
        async with sem:
            return await _process_single_repo(
                provider,
                github_id,
                org_settings,
                repo_name,
                jsonnet_config,
                teams,
                app_installations,
            )

    if concurrency is not None:
        chunk_size = 50
        result = []
        for chunk in divide_chunks(repo_names, chunk_size):
            result.extend(await asyncio.gather(*[safe_process(repo_name) for repo_name in chunk]))

            # after processing a full chunk, wait for 30s to avoid hitting secondary rate limits
            if len(chunk) == chunk_size:
                await asyncio.sleep(30)
    else:
        result = await asyncio.gather(*[safe_process(repo_name) for repo_name in repo_names])

    for data in result:
        _, repo_data = data
        yield repo_data


def divide_chunks(input_list, n):
    # looping till length of input_list
    for i in range(0, len(input_list), n):
        yield input_list[i : i + n]
