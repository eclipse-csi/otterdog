# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

import dataclasses
from typing import Any, ClassVar, Optional, Iterator, cast, Callable

from jsonbender import bend, S, OptionalS, K, Forall  # type: ignore

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import ModelObject, ValidationContext, FailureType
from otterdog.providers.github import Github
from otterdog.utils import UNSET, is_unset, IndentingPrinter, write_patch_object_as_json

from .branch_protection_rule import BranchProtectionRule
from .environment import Environment
from .repo_secret import RepositorySecret
from .repo_webhook import RepositoryWebhook


@dataclasses.dataclass
class Repository(ModelObject):
    """
    Represents a Repository of an Organization.
    """

    id: int = dataclasses.field(metadata={"external_only": True})
    node_id: str = dataclasses.field(metadata={"external_only": True})
    name: str = dataclasses.field(metadata={"key": True})
    description: Optional[str]
    homepage: Optional[str]
    private: bool
    has_discussions: bool
    has_issues: bool
    has_projects: bool
    has_wiki: bool
    is_template: bool
    template_repository: Optional[str] = dataclasses.field(metadata={"read_only": True})
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

    # model only fields
    aliases: list[str] = dataclasses.field(metadata={"model_only": True}, default_factory=list)
    post_process_template_content: list[str] = dataclasses.field(metadata={"model_only": True}, default_factory=list)
    auto_init: bool = dataclasses.field(metadata={"model_only": True}, default=False)

    # nested model fields
    webhooks: list[RepositoryWebhook] = dataclasses.field(metadata={"nested_model": True}, default_factory=list)
    secrets: list[RepositorySecret] = dataclasses.field(metadata={"nested_model": True}, default_factory=list)
    branch_protection_rules: list[BranchProtectionRule] = dataclasses.field(
        metadata={"nested_model": True}, default_factory=list
    )
    environments: list[Environment] = dataclasses.field(metadata={"nested_model": True}, default_factory=list)

    _security_properties: ClassVar[list[str]] = [
        "secret_scanning",
        "secret_scanning_push_protection",
    ]

    _unavailable_fields_in_archived_repos: ClassVar[set[str]] = {
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
        "secret_scanning_push_protection",
    }

    @property
    def model_object_name(self) -> str:
        return "repository"

    def get_all_names(self) -> list[str]:
        return [self.name] + self.aliases

    def add_branch_protection_rule(self, rule: BranchProtectionRule) -> None:
        self.branch_protection_rules.append(rule)

    def set_branch_protection_rules(self, rules: list[BranchProtectionRule]) -> None:
        self.branch_protection_rules = rules

    def add_webhook(self, webhook: RepositoryWebhook) -> None:
        self.webhooks.append(webhook)

    def get_webhook(self, url: str) -> Optional[RepositoryWebhook]:
        for webhook in self.webhooks:
            if webhook.url == url:
                return webhook

        return None

    def set_webhooks(self, webhooks: list[RepositoryWebhook]) -> None:
        self.webhooks = webhooks

    def add_secret(self, secret: RepositorySecret) -> None:
        self.secrets.append(secret)

    def get_secret(self, name: str) -> Optional[RepositorySecret]:
        for secret in self.secrets:
            if secret.name == name:
                return secret

        return None

    def set_secrets(self, secrets: list[RepositorySecret]) -> None:
        self.secrets = secrets

    def add_environment(self, environment: Environment) -> None:
        self.environments.append(environment)

    def set_environments(self, environments: list[Environment]) -> None:
        self.environments = environments

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

        if is_public and disallow_forking:
            context.add_failure(
                FailureType.WARNING,
                f"public {self.get_model_header()} has 'allow_forking' disabled " f"which is not permitted.",
            )

        has_wiki = self.has_wiki is True
        if is_private and has_wiki and free_plan:
            context.add_failure(
                FailureType.WARNING,
                f"private {self.get_model_header()} has 'has_wiki' enabled which"
                f"requires at least GitHub Team billing, "
                f'currently using "{org_settings.plan}" plan.',
            )

        has_discussions_disabled = self.has_discussions is False
        if has_discussions_disabled and org_has_discussions_enabled_with_repo_as_source:
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header()} has 'has_discussions' disabled "
                f"while the organization uses this repo as source repository for discussions.",
            )

        has_projects = self.has_projects is True
        if has_projects and org_has_projects_disabled:
            context.add_failure(
                FailureType.INFO,
                f"{self.get_model_header()} has 'has_projects' enabled "
                f"while the organization disables 'has_organization_projects', setting will be ignored.",
            )

        if is_private and org_members_cannot_fork_private_repositories and allow_forking:
            context.add_failure(
                FailureType.ERROR,
                f"private {self.get_model_header()} has 'allow_forking' enabled "
                f"while the organization disables 'members_can_fork_private_repositories'.",
            )

        repo_web_commit_signoff_not_required = self.web_commit_signoff_required is False
        if repo_web_commit_signoff_not_required and org_web_commit_signoff_required:
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header()} has 'web_commit_signoff_required' disabled while "
                f"the organization requires it.",
            )

        secret_scanning_disabled = self.secret_scanning == "disabled"
        secret_scanning_push_protection_enabled = self.secret_scanning_push_protection == "enabled"
        if secret_scanning_disabled and secret_scanning_push_protection_enabled and self.archived is False:
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header()} has 'secret_scanning' disabled while "
                f"'secret_scanning_push_protection' is enabled.",
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

        for secret in self.secrets:
            secret.validate(context, self)

        for bpr in self.branch_protection_rules:
            bpr.validate(context, self)

        for env in self.environments:
            env.validate(context, self)

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        # private repos don't support security analysis.
        if self.private is True:
            if field.name in self._security_properties:
                return False

        if self.archived is True:
            if field.name in self._unavailable_fields_in_archived_repos:
                return False

        return True

    def get_model_objects(self) -> Iterator[tuple[ModelObject, ModelObject]]:
        for webhook in self.webhooks:
            yield webhook, self
            yield from webhook.get_model_objects()

        for secret in self.secrets:
            yield secret, self
            yield from secret.get_model_objects()

        for rule in self.branch_protection_rules:
            yield rule, self
            yield from rule.get_model_objects()

        for env in self.environments:
            yield env, self
            yield from env.get_model_objects()

    @classmethod
    def from_model_data(cls, data: dict[str, Any]) -> Repository:
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}

        mapping.update(
            {
                "webhooks": OptionalS("webhooks", default=[]) >> Forall(lambda x: RepositoryWebhook.from_model_data(x)),
                "secrets": OptionalS("secrets", default=[]) >> Forall(lambda x: RepositorySecret.from_model_data(x)),
                "branch_protection_rules": OptionalS("branch_protection_rules", default=[])
                >> Forall(lambda x: BranchProtectionRule.from_model_data(x)),
                "environments": OptionalS("environments", default=[])
                >> Forall(lambda x: Environment.from_model_data(x)),
            }
        )

        return cls(**bend(mapping, data))

    @classmethod
    def from_provider_data(cls, org_id: str, data: dict[str, Any]) -> Repository:
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}

        mapping.update(
            {
                "webhooks": K([]),
                "secrets": K([]),
                "branch_protection_rules": K([]),
                "environments": K([]),
                "secret_scanning": OptionalS("security_and_analysis", "secret_scanning", "status", default=UNSET),
                "secret_scanning_push_protection": OptionalS(
                    "security_and_analysis",
                    "secret_scanning_push_protection",
                    "status",
                    default=UNSET,
                ),
                "template_repository": OptionalS("template_repository", "full_name", default=None),
            }
        )

        return cls(**bend(mapping, data))

    @classmethod
    def _to_provider_data(cls, org_id: str, data: dict[str, Any], provider: Github) -> dict[str, Any]:
        mapping = {
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
                    security_mapping[security_prop] = {"status": S(security_prop)}

            if len(security_mapping) > 0:
                mapping.update({"security_and_analysis": security_mapping})

        return bend(mapping, data)

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

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        jsonnet_config: JsonnetConfig,
        extend: bool,
        default_object: ModelObject,
    ) -> None:
        patch = self.get_patch_to(default_object)

        has_webhooks = len(self.webhooks) > 0
        has_secrets = len(self.secrets) > 0
        has_branch_protection_rules = len(self.branch_protection_rules) > 0
        has_environments = len(self.environments) > 0

        # FIXME: take webhooks, branch protection rules and environments into account once
        #        it is supported for repos that get extended.
        has_changes = len(patch) > 0
        if extend and has_changes is False:
            return

        if "name" in patch:
            patch.pop("name")

        function = f"orgs.{jsonnet_config.extend_repo}" if extend else f"orgs.{jsonnet_config.create_repo}"
        printer.print(f"{function}('{self.name}')")

        write_patch_object_as_json(patch, printer, close_object=False)

        # FIXME: support overriding webhooks for repos coming from the default configuration.
        if has_webhooks and not extend:
            default_repo_webhook = RepositoryWebhook.from_model_data(jsonnet_config.default_repo_webhook_config)

            printer.println("webhooks: [")
            printer.level_up()

            for webhook in self.webhooks:
                webhook.to_jsonnet(printer, jsonnet_config, False, default_repo_webhook)

            printer.level_down()
            printer.println("],")

        # FIXME: support overriding secrets for repos coming from the default configuration.
        if has_secrets and not extend:
            default_repo_secret = RepositorySecret.from_model_data(jsonnet_config.default_repo_secret_config)

            printer.println("secrets: [")
            printer.level_up()

            for secret in self.secrets:
                secret.to_jsonnet(printer, jsonnet_config, False, default_repo_secret)

            printer.level_down()
            printer.println("],")

        # FIXME: support overriding branch protection rules for repos coming from
        #        the default configuration.
        if has_branch_protection_rules and not extend:
            default_org_rule = BranchProtectionRule.from_model_data(jsonnet_config.default_branch_config)

            printer.println("branch_protection_rules: [")
            printer.level_up()

            for rule in self.branch_protection_rules:
                rule.to_jsonnet(printer, jsonnet_config, False, default_org_rule)

            printer.level_down()
            printer.println("],")

        # FIXME: support overriding environments for repos coming from
        #        the default configuration.
        if has_environments and not extend:
            default_environment = Environment.from_model_data(jsonnet_config.default_environment_config)

            printer.println("environments: [")
            printer.level_up()

            for env in self.environments:
                env.to_jsonnet(printer, jsonnet_config, False, default_environment)

            printer.level_down()
            printer.println("],")

        # close the repo object
        printer.level_down()
        printer.println("},")
