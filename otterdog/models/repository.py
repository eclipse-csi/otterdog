#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Iterator
from typing import Any, ClassVar, cast

from jsonbender import F, Forall, If, K, OptionalS, S, bend  # type: ignore

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import (
    FailureType,
    LivePatch,
    LivePatchContext,
    LivePatchHandler,
    LivePatchType,
    ModelObject,
    PatchContext,
    ValidationContext,
)
from otterdog.providers.github import GitHubProvider
from otterdog.utils import (
    UNSET,
    Change,
    IndentingPrinter,
    is_set_and_present,
    is_set_and_valid,
    is_unset,
    write_patch_object_as_json,
)

from .branch_protection_rule import BranchProtectionRule
from .environment import Environment
from .organization_settings import OrganizationSettings
from .repo_ruleset import RepositoryRuleset
from .repo_secret import RepositorySecret
from .repo_variable import RepositoryVariable
from .repo_webhook import RepositoryWebhook
from .repo_workflow_settings import RepositoryWorkflowSettings


@dataclasses.dataclass
class Repository(ModelObject):
    """
    Represents a Repository of an Organization.
    """

    id: int = dataclasses.field(metadata={"external_only": True})
    node_id: str = dataclasses.field(metadata={"external_only": True})
    name: str = dataclasses.field(metadata={"key": True})
    description: str | None
    homepage: str | None
    private: bool
    has_discussions: bool
    has_issues: bool
    has_projects: bool
    has_wiki: bool
    is_template: bool
    template_repository: str | None = dataclasses.field(metadata={"read_only": True})
    topics: list[str]
    default_branch: str
    allow_rebase_merge: bool
    allow_merge_commit: bool
    allow_squash_merge: bool
    allow_auto_merge: bool
    delete_branch_on_merge: bool
    allow_update_branch: bool
    squash_merge_commit_title: str
    squash_merge_commit_message: str
    merge_commit_title: str
    merge_commit_message: str
    archived: bool
    allow_forking: bool
    web_commit_signoff_required: bool
    secret_scanning: str
    secret_scanning_push_protection: str
    dependabot_alerts_enabled: bool
    dependabot_security_updates_enabled: bool
    private_vulnerability_reporting_enabled: bool

    gh_pages_build_type: str
    gh_pages_source_branch: str | None
    gh_pages_source_path: str | None

    forked_repository: str | None = dataclasses.field(metadata={"model_only": True})
    fork_default_branch_only: bool = dataclasses.field(metadata={"model_only": True})

    workflows: RepositoryWorkflowSettings = dataclasses.field(metadata={"nested_model": True})

    # model only fields
    aliases: list[str] = dataclasses.field(metadata={"model_only": True}, default_factory=list)
    post_process_template_content: list[str] = dataclasses.field(metadata={"model_only": True}, default_factory=list)
    auto_init: bool = dataclasses.field(metadata={"model_only": True}, default=False)

    # nested model fields
    webhooks: list[RepositoryWebhook] = dataclasses.field(metadata={"nested_model": True}, default_factory=list)
    secrets: list[RepositorySecret] = dataclasses.field(metadata={"nested_model": True}, default_factory=list)
    variables: list[RepositoryVariable] = dataclasses.field(metadata={"nested_model": True}, default_factory=list)
    branch_protection_rules: list[BranchProtectionRule] = dataclasses.field(
        metadata={"nested_model": True}, default_factory=list
    )
    rulesets: list[RepositoryRuleset] = dataclasses.field(metadata={"nested_model": True}, default_factory=list)
    environments: list[Environment] = dataclasses.field(metadata={"nested_model": True}, default_factory=list)

    _security_properties: ClassVar[list[str]] = [
        "secret_scanning",
        "secret_scanning_push_protection",
        "dependabot_security_updates_enabled",
    ]

    _additional_security_properties: ClassVar[list[str]] = [
        "private_vulnerability_reporting_enabled",
    ]

    _unavailable_fields_in_archived_repos: ClassVar[set[str]] = {
        "description",
        "homepage",
        "allow_auto_merge",
        "allow_merge_commit",
        "allow_rebase_merge",
        "allow_squash_merge",
        "allow_update_branch",
        "delete_branch_on_merge",
        "merge_commit_message",
        "merge_commit_title",
        "squash_merge_commit_message",
        "squash_merge_commit_title",
        "dependabot_alerts_enabled",
        "dependabot_security_updates_enabled",
        "private_vulnerability_reporting_enabled",
        "secret_scanning",
        "secret_scanning_push_protection",
        "has_issues",
        "has_wiki",
        "has_projects",
    }

    _gh_pages_properties: ClassVar[list[str]] = [
        "gh_pages_source_branch",
        "gh_pages_source_path",
    ]

    @property
    def model_object_name(self) -> str:
        return "repository"

    def get_all_names(self) -> list[str]:
        return [self.name] + self.aliases

    def get_all_key_values(self) -> list[Any]:
        return self.get_all_names()

    def add_branch_protection_rule(self, rule: BranchProtectionRule) -> None:
        self.branch_protection_rules.append(rule)

    def set_branch_protection_rules(self, rules: list[BranchProtectionRule]) -> None:
        self.branch_protection_rules = rules

    def add_ruleset(self, rule: RepositoryRuleset) -> None:
        self.rulesets.append(rule)

    def set_rulesets(self, rules: list[RepositoryRuleset]) -> None:
        self.rulesets = rules

    def add_webhook(self, webhook: RepositoryWebhook) -> None:
        self.webhooks.append(webhook)

    def get_webhook(self, url: str) -> RepositoryWebhook | None:
        return next(filter(lambda x: x.url == url, self.webhooks), None)  # type: ignore

    def set_webhooks(self, webhooks: list[RepositoryWebhook]) -> None:
        self.webhooks = webhooks

    def add_secret(self, secret: RepositorySecret) -> None:
        self.secrets.append(secret)

    def get_secret(self, name: str) -> RepositorySecret | None:
        return next(filter(lambda x: x.name == name, self.secrets), None)  # type: ignore

    def set_secrets(self, secrets: list[RepositorySecret]) -> None:
        self.secrets = secrets

    def add_variable(self, variable: RepositoryVariable) -> None:
        self.variables.append(variable)

    def get_variable(self, name: str) -> RepositoryVariable | None:
        return next(filter(lambda x: x.name == name, self.variables), None)  # type: ignore

    def set_variables(self, variables: list[RepositoryVariable]) -> None:
        self.variables = variables

    def add_environment(self, environment: Environment) -> None:
        self.environments.append(environment)

    def set_environments(self, environments: list[Environment]) -> None:
        self.environments = environments

    def coerce_from_org_settings(self, org_settings: OrganizationSettings) -> Repository:
        copy = dataclasses.replace(self)

        if org_settings.has_organization_projects is False:
            copy.has_projects = UNSET  # type: ignore

        if org_settings.web_commit_signoff_required is True:
            copy.web_commit_signoff_required = UNSET  # type: ignore

        return copy

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        from .github_organization import GitHubOrganization

        github_id = cast(GitHubOrganization, parent_object).github_id
        org_settings = cast(GitHubOrganization, parent_object).settings

        free_plan = org_settings.plan == "free"

        org_has_projects_disabled = org_settings.has_organization_projects is False
        org_web_commit_signoff_required = org_settings.web_commit_signoff_required is True
        org_members_cannot_fork_private_repositories = org_settings.members_can_fork_private_repositories is False

        org_has_discussions_enabled_with_repo_as_source = (
            org_settings.has_discussions is True
            and org_settings.discussion_source_repository == f"{github_id}/{self.name}"
        )

        is_private = self.private is True
        is_public = self.private is False

        allow_forking = self.allow_forking is True
        disallow_forking = self.allow_forking is False

        if is_set_and_present(self.description) and len(self.description) > 350:
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header()} has 'description' that exceeds the maximum allowed length of 350 chars.",
            )

        if is_set_and_valid(self.topics):
            if len(self.topics) > 20:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header()} has more than 20 'topics' defined.",
                )

            for topic in self.topics:
                if not self._valid_topic(topic):
                    context.add_failure(
                        FailureType.ERROR,
                        f"{self.get_model_header()} has defined an invalid topic '{topic}'. "
                        f"Only lower-case, numbers and '-' are allowed characters.",
                    )

        if is_public and disallow_forking:
            context.add_failure(
                FailureType.WARNING,
                f"public {self.get_model_header()} has 'allow_forking' disabled which is not permitted.",
            )

        has_wiki = self.has_wiki is True
        if is_private and has_wiki and free_plan:
            context.add_failure(
                FailureType.WARNING,
                f"private {self.get_model_header()} has 'has_wiki' enabled which"
                f"requires at least GitHub Team billing, "
                f"currently using '{org_settings.plan}' plan.",
            )

        has_discussions_disabled = self.has_discussions is False
        if has_discussions_disabled and org_has_discussions_enabled_with_repo_as_source:
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header()} has 'has_discussions' disabled "
                f"while the organization uses this repo as source repository for discussions.",
            )

        # it seems that 'has_repository_projects' is not really taken into account,
        # the setting 'has_organization_projects' is used to control whether repos can actually have projects.
        if self.has_projects is True and org_has_projects_disabled:
            context.add_failure(
                FailureType.WARNING,
                f"{self.get_model_header()} has 'has_projects' enabled "
                f"while the organization disables 'has_organization_projects', setting will be ignored.",
            )

        if is_private and org_members_cannot_fork_private_repositories and allow_forking:
            context.add_failure(
                FailureType.ERROR,
                f"private {self.get_model_header()} has 'allow_forking' enabled "
                f"while the organization disables 'members_can_fork_private_repositories'.",
            )

        if self.web_commit_signoff_required is False and org_web_commit_signoff_required:
            context.add_failure(
                FailureType.WARNING,
                f"{self.get_model_header()} has 'web_commit_signoff_required' disabled while "
                f"the organization requires it, setting will be ignored.",
            )

        secret_scanning_disabled = self.secret_scanning == "disabled"
        secret_scanning_push_protection_enabled = self.secret_scanning_push_protection == "enabled"
        if secret_scanning_disabled and secret_scanning_push_protection_enabled and self.archived is False:
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header()} has 'secret_scanning' disabled while "
                f"'secret_scanning_push_protection' is enabled.",
            )

        if is_set_and_valid(self.template_repository) and is_set_and_valid(self.forked_repository):
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header()} has 'template_repository' and 'forked_repository' set at the same time.",
            )

        for webhook in self.webhooks:
            webhook.validate(context, self)

        if self.archived is True:
            if len(self.branch_protection_rules) > 0:
                context.add_failure(
                    FailureType.INFO,
                    f"{self.get_model_header()} is archived but has branch_protection_rules, "
                    f"rules will be ignored.",
                )

        if self.name.lower() == f"{github_id}.github.io".lower():
            if self.gh_pages_build_type == "disabled":
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has"
                    f" 'gh_pages_build_type' disabled but the repo hosts the organization site and"
                    f" GitHub pages will be enabled automatically.\n"
                    f" Add the following snippet to your repo configuration:\n\n"
                    f'   gh_pages_build_type: "legacy",\n'
                    f'   gh_pages_source_branch: "main",\n'
                    f'   gh_pages_source_path: "/",',
                )

            if len(list(filter(lambda x: x.name == "github-pages", self.environments))) == 0:
                context.add_failure(
                    FailureType.WARNING,
                    f"{self.get_model_header(parent_object)} hosts the organization site"
                    f" but no corresponding 'github-pages' environment, please add such an environment.\n"
                    f" Add the following snippet to the repo configuration:\n\n"
                    f"   environments: [\n"
                    f"     orgs.newEnvironment('github-pages') {{\n"
                    f"       branch_policies+: [\n"
                    f'         "main"\n'
                    f"       ],\n"
                    f'       deployment_branch_policy: "selected",\n'
                    f"     }},\n"
                    f"   ],",
                )
        elif is_set_and_valid(self.gh_pages_build_type):
            if self.gh_pages_build_type not in {"disabled", "legacy", "workflow"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"'gh_pages_build_type' has value '{self.gh_pages_build_type}', "
                    f"only values ('disabled' | 'legacy' | 'workflow') are allowed.",
                )

            if self.gh_pages_build_type == "disabled":
                for key in self._gh_pages_properties:
                    value = self.__getattribute__(key)
                    if value is not None:
                        context.add_failure(
                            FailureType.WARNING,
                            f"{self.get_model_header(parent_object)} has"
                            f" 'gh_pages_build_type' disabled but '{key}' "
                            f"is set to a value '{value}', setting will be ignored.",
                        )

            if self.gh_pages_build_type in {"legacy", "workflow"}:
                if len(list(filter(lambda x: x.name == "github-pages", self.environments))) == 0:
                    context.add_failure(
                        FailureType.WARNING,
                        f"{self.get_model_header(parent_object)} has"
                        f" 'gh_pages_build_type' with value '{self.gh_pages_build_type}' "
                        f"but no corresponding 'github-pages' environment, please add such an environment.",
                    )

        if is_set_and_valid(self.workflows):
            self.workflows.validate(context, self)

        for secret in self.secrets:
            secret.validate(context, self)

        for variable in self.variables:
            variable.validate(context, self)

        for bpr in self.branch_protection_rules:
            bpr.validate(context, self)

        for rule in self.rulesets:
            rule.validate(context, self)

        for env in self.environments:
            env.validate(context, self)

    @staticmethod
    def _valid_topic(topic, search=re.compile(r"[^a-z0-9\-]").search):
        return not bool(search(topic))

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        # private repos don't support security analysis.
        if self.private is True:
            if field.name in self._security_properties or field.name in self._additional_security_properties:
                return False

        if self.archived is True:
            if field.name in self._unavailable_fields_in_archived_repos:
                return False

        if self.gh_pages_build_type in ["disabled", "workflow"]:
            if field.name in self._gh_pages_properties:
                return False

        return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        # private repos don't support security analysis.
        if self.private is True:
            if field.name in self._security_properties:
                return False

        if self.gh_pages_build_type in ["disabled", "workflow"]:
            if field.name in self._gh_pages_properties:
                return False

        # when generating a patch, capture all the current configuration, even for
        # archived repos, the properties might be used when the repo gets unarchived.
        return True

    def get_model_objects(self) -> Iterator[tuple[ModelObject, ModelObject]]:
        for webhook in self.webhooks:
            yield webhook, self
            yield from webhook.get_model_objects()

        for secret in self.secrets:
            yield secret, self
            yield from secret.get_model_objects()

        for variable in self.variables:
            yield variable, self
            yield from variable.get_model_objects()

        for bpr in self.branch_protection_rules:
            yield bpr, self
            yield from bpr.get_model_objects()

        for ruleset in self.rulesets:
            yield ruleset, self
            yield from ruleset.get_model_objects()

        for env in self.environments:
            yield env, self
            yield from env.get_model_objects()

        if is_set_and_valid(self.workflows):
            yield self.workflows, self

    @classmethod
    def from_model_data(cls, data: dict[str, Any]) -> Repository:
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}

        mapping.update(
            {
                "webhooks": OptionalS("webhooks", default=[]) >> Forall(lambda x: RepositoryWebhook.from_model_data(x)),
                "secrets": OptionalS("secrets", default=[]) >> Forall(lambda x: RepositorySecret.from_model_data(x)),
                "variables": OptionalS("variables", default=[])
                >> Forall(lambda x: RepositoryVariable.from_model_data(x)),
                "branch_protection_rules": OptionalS("branch_protection_rules", default=[])
                >> Forall(lambda x: BranchProtectionRule.from_model_data(x)),
                "rulesets": OptionalS("rulesets", default=[]) >> Forall(lambda x: RepositoryRuleset.from_model_data(x)),
                "environments": OptionalS("environments", default=[])
                >> Forall(lambda x: Environment.from_model_data(x)),
                "workflows": If(
                    OptionalS("workflows", default=None) == K(None),
                    K(UNSET),
                    S("workflows") >> F(lambda x: RepositoryWorkflowSettings.from_model_data(x)),
                ),
            }
        )

        return cls(**bend(mapping, data))

    @classmethod
    def from_provider_data(cls, org_id: str, data: dict[str, Any]) -> Repository:
        mapping = cls.get_mapping_from_provider(org_id, data)
        return cls(**bend(mapping, data))

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}

        def status_to_bool(status):
            if status == "enabled":
                return True
            elif status == "disabled":
                return False
            else:
                return UNSET

        # mapping for gh-pages config
        mapping.update(
            {
                "gh_pages_build_type": OptionalS("gh_pages", "build_type", default="disabled"),
                "gh_pages_source_branch": OptionalS("gh_pages", "source", "branch", default=None),
                "gh_pages_source_path": OptionalS("gh_pages", "source", "path", default=None),
            }
        )

        mapping.update(
            {
                "webhooks": K([]),
                "secrets": K([]),
                "variables": K([]),
                "branch_protection_rules": K([]),
                "rulesets": K([]),
                "environments": K([]),
                "secret_scanning": OptionalS("security_and_analysis", "secret_scanning", "status", default=UNSET),
                "secret_scanning_push_protection": OptionalS(
                    "security_and_analysis",
                    "secret_scanning_push_protection",
                    "status",
                    default=UNSET,
                ),
                "dependabot_security_updates_enabled": OptionalS(
                    "security_and_analysis", "dependabot_security_updates", "status", default=UNSET
                )
                >> F(status_to_bool),
                "template_repository": OptionalS("template_repository", "full_name", default=None),
            }
        )
        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping: dict[str, Any] = {
            field.name: S(field.name) for field in cls.provider_fields() if not is_unset(data.get(field.name, UNSET))
        }

        # add mapping for items that GitHub expects in a nested structure.

        # private repos do not support secret scanning settings, remove them.
        is_private = data.get("private", False)
        if is_private:
            for security_prop in cls._security_properties:
                if security_prop in mapping:
                    mapping.pop(security_prop)
        else:
            security_mapping = {}
            for security_prop in cls._security_properties:
                if security_prop in mapping:
                    mapping.pop(security_prop)
                if security_prop in data:
                    if security_prop.endswith("_enabled"):
                        github_security_prop = security_prop.removesuffix("_enabled")
                        security_mapping[github_security_prop] = {
                            "status": If(S(security_prop) == K(True), K("enabled"), K("disabled"))
                        }
                    else:
                        security_mapping[security_prop] = {"status": S(security_prop)}

            if len(security_mapping) > 0:
                mapping.update({"security_and_analysis": security_mapping})

        gh_pages_mapping = {}
        if "gh_pages_build_type" in data:
            mapping.pop("gh_pages_build_type")
            gh_pages_mapping["build_type"] = S("gh_pages_build_type")

        gh_pages_build_type = data.get("gh_pages_build_type", None)

        if gh_pages_build_type is None or gh_pages_build_type == "legacy":
            gh_pages_legacy_mapping = {}
            for source_prop in ["gh_pages_source_branch", "gh_pages_source_path"]:
                if source_prop in data:
                    mapping.pop(source_prop)
                    key = source_prop.rsplit("_")[-1]
                    gh_pages_legacy_mapping[key] = S(source_prop)

            if len(gh_pages_legacy_mapping) > 0:
                gh_pages_mapping["source"] = gh_pages_legacy_mapping

        if len(gh_pages_mapping) > 0:
            mapping["gh_pages"] = gh_pages_mapping

        return mapping

    def resolve_secrets(self, secret_resolver: Callable[[str], str]) -> None:
        for webhook in self.webhooks:
            webhook.resolve_secrets(secret_resolver)

        for secret in self.secrets:
            secret.resolve_secrets(secret_resolver)

    def copy_secrets(self, other_object: ModelObject) -> None:
        for webhook in self.webhooks:
            other_repo = cast(Repository, other_object)
            other_webhook = other_repo.get_webhook(webhook.url)
            if other_webhook is not None:
                webhook.copy_secrets(other_webhook)

        for secret in self.secrets:
            other_repo = cast(Repository, other_object)
            other_secret = other_repo.get_secret(secret.name)
            if other_secret is not None:
                secret.copy_secrets(other_secret)

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.extend_repo}" if extend else f"orgs.{jsonnet_config.create_repo}"

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        jsonnet_config: JsonnetConfig,
        context: PatchContext,
        extend: bool,
        default_object: ModelObject,
    ) -> None:
        patch = self.get_patch_to(default_object)

        has_webhooks = len(self.webhooks) > 0
        has_secrets = len(self.secrets) > 0
        has_variables = len(self.variables) > 0
        has_branch_protection_rules = len(self.branch_protection_rules) > 0
        has_rulesets = len(self.rulesets) > 0
        has_environments = len(self.environments) > 0

        # FIXME: take webhooks, branch protection rules and environments into account once
        #        it is supported for repos that get extended.
        has_changes = len(patch) > 0
        if extend and has_changes is False:
            return

        if "name" in patch:
            patch.pop("name")

        function = self.get_jsonnet_template_function(jsonnet_config, extend)
        printer.print(f"{function}('{self.name}')")

        write_patch_object_as_json(patch, printer, close_object=False)

        if is_set_and_present(self.workflows):
            default_workflow_settings = cast(Repository, default_object).workflows

            if is_set_and_valid(default_workflow_settings):
                coerced_settings = self.workflows.coerce_from_org_settings(
                    self, cast(OrganizationSettings, context.org_settings).workflows
                )
                patch = coerced_settings.get_patch_to(default_workflow_settings)
                if len(patch) > 0:
                    printer.print("workflows+:")
                    coerced_settings.to_jsonnet(printer, jsonnet_config, context, False, default_workflow_settings)

        # FIXME: support overriding webhooks for repos coming from the default configuration.
        if has_webhooks and not extend:
            default_repo_webhook = RepositoryWebhook.from_model_data(jsonnet_config.default_repo_webhook_config)

            printer.println("webhooks: [")
            printer.level_up()

            for webhook in self.webhooks:
                webhook.to_jsonnet(printer, jsonnet_config, context, False, default_repo_webhook)

            printer.level_down()
            printer.println("],")

        # FIXME: support overriding secrets for repos coming from the default configuration.
        if has_secrets and not extend:
            default_repo_secret = RepositorySecret.from_model_data(jsonnet_config.default_repo_secret_config)

            printer.println("secrets: [")
            printer.level_up()

            for secret in self.secrets:
                secret.to_jsonnet(printer, jsonnet_config, context, False, default_repo_secret)

            printer.level_down()
            printer.println("],")

        # FIXME: support overriding variables for repos coming from the default configuration.
        if has_variables and not extend:
            default_repo_variable = RepositoryVariable.from_model_data(jsonnet_config.default_repo_variable_config)

            printer.println("variables: [")
            printer.level_up()

            for variable in self.variables:
                variable.to_jsonnet(printer, jsonnet_config, context, False, default_repo_variable)

            printer.level_down()
            printer.println("],")

        # FIXME: support overriding branch protection rules for repos coming from
        #        the default configuration.
        if has_branch_protection_rules and not extend:
            default_org_rule = BranchProtectionRule.from_model_data(
                jsonnet_config.default_branch_protection_rule_config
            )

            printer.println("branch_protection_rules: [")
            printer.level_up()

            for rule in self.branch_protection_rules:
                rule.to_jsonnet(printer, jsonnet_config, context, False, default_org_rule)

            printer.level_down()
            printer.println("],")

        # FIXME: support overriding rulesets for repos coming from the default configuration.
        if has_rulesets and not extend:
            default_org_rule = RepositoryRuleset.from_model_data(jsonnet_config.default_repo_ruleset_config)

            printer.println("rulesets: [")
            printer.level_up()

            for ruleset in self.rulesets:
                ruleset.to_jsonnet(printer, jsonnet_config, context, False, default_org_rule)

            printer.level_down()
            printer.println("],")

        # FIXME: support overriding environments for repos coming from
        #        the default configuration.
        if has_environments and not extend:
            default_environment = Environment.from_model_data(jsonnet_config.default_environment_config)

            printer.println("environments: [")
            printer.level_up()

            for env in self.environments:
                env.to_jsonnet(printer, jsonnet_config, context, False, default_environment)

            printer.level_down()
            printer.println("],")

        # close the repo object
        printer.level_down()
        printer.println("},")

    @classmethod
    def generate_live_patch(
        cls,
        expected_object: ModelObject | None,
        current_object: ModelObject | None,
        parent_object: ModelObject | None,
        context: LivePatchContext,
        handler: LivePatchHandler,
    ) -> None:
        if expected_object is None:
            assert isinstance(current_object, Repository)
            handler(LivePatch.of_deletion(current_object, parent_object, current_object.apply_live_patch))
            return

        assert isinstance(expected_object, Repository)

        expected_org_settings = cast(OrganizationSettings, context.expected_org_settings)
        coerced_object = expected_object.coerce_from_org_settings(expected_org_settings)

        if current_object is None:
            handler(LivePatch.of_addition(coerced_object, parent_object, coerced_object.apply_live_patch))
        else:
            assert isinstance(current_object, Repository)

            modified_repo: dict[str, Change[Any]] = coerced_object.get_difference_from(current_object)

            # FIXME: needed to add this hack to ensure that gh_pages_source_path is also present in
            #        the modified data as GitHub needs the path as well when the branch is changed.
            #        this needs to make clean to support making the diff operation generic as possible.
            if "gh_pages_source_branch" in modified_repo:
                gh_pages_source_path = cast(Repository, coerced_object).gh_pages_source_path
                modified_repo["gh_pages_source_path"] = Change(gh_pages_source_path, gh_pages_source_path)

            # similar fix as above for squash_merge_commit_title as well
            if "squash_merge_commit_title" in modified_repo:
                squash_merge_commit_message = cast(Repository, coerced_object).squash_merge_commit_message
                modified_repo["squash_merge_commit_message"] = Change(
                    squash_merge_commit_message, squash_merge_commit_message
                )

            if len(modified_repo) > 0:
                handler(
                    LivePatch.of_changes(
                        coerced_object,
                        current_object,
                        modified_repo,
                        parent_object,
                        False,
                        coerced_object.apply_live_patch,
                    )
                )

        parent_repo = coerced_object if current_object is None else current_object

        if is_set_and_valid(coerced_object.workflows):
            RepositoryWorkflowSettings.generate_live_patch(
                coerced_object.workflows,
                current_object.workflows if current_object is not None else None,
                parent_repo,
                context,
                handler,
            )

        RepositoryWebhook.generate_live_patch_of_list(
            coerced_object.webhooks,
            current_object.webhooks if current_object is not None else [],
            parent_repo,
            context,
            handler,
        )

        RepositorySecret.generate_live_patch_of_list(
            coerced_object.secrets,
            current_object.secrets if current_object is not None else [],
            parent_repo,
            context,
            handler,
        )

        RepositoryVariable.generate_live_patch_of_list(
            coerced_object.variables,
            current_object.variables if current_object is not None else [],
            parent_repo,
            context,
            handler,
        )

        Environment.generate_live_patch_of_list(
            coerced_object.environments,
            current_object.environments if current_object is not None else [],
            parent_repo,
            context,
            handler,
        )

        # only take branch protection rules of non-archive projects into account
        if coerced_object.archived is False:
            BranchProtectionRule.generate_live_patch_of_list(
                coerced_object.branch_protection_rules,
                current_object.branch_protection_rules if current_object is not None else [],
                parent_repo,
                context,
                handler,
            )

            RepositoryRuleset.generate_live_patch_of_list(
                coerced_object.rulesets,
                current_object.rulesets if current_object is not None else [],
                parent_repo,
                context,
                handler,
            )

    @classmethod
    async def apply_live_patch(cls, patch: LivePatch, org_id: str, provider: GitHubProvider) -> None:
        match patch.patch_type:
            case LivePatchType.ADD:
                assert isinstance(patch.expected_object, Repository)
                await provider.add_repo(
                    org_id,
                    await patch.expected_object.to_provider_data(org_id, provider),
                    patch.expected_object.template_repository,
                    patch.expected_object.post_process_template_content,
                    patch.expected_object.forked_repository,
                    patch.expected_object.fork_default_branch_only,
                    patch.expected_object.auto_init,
                )

            case LivePatchType.REMOVE:
                assert isinstance(patch.current_object, Repository)
                await provider.delete_repo(org_id, patch.current_object.name)

            case LivePatchType.CHANGE:
                assert patch.changes is not None
                assert isinstance(patch.expected_object, Repository)
                assert isinstance(patch.current_object, Repository)
                await provider.update_repo(
                    org_id,
                    patch.current_object.name,
                    await cls.changes_to_provider(org_id, patch.changes, provider),
                )
