# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from dataclasses import dataclass, field as dataclass_field, Field
from typing import Any, ClassVar, Union

from jsonbender import bend, S, OptionalS, K, Forall

from otterdog.providers.github import Github
from otterdog.utils import UNSET, is_unset

from . import ModelObject, ValidationContext, FailureType
from .organization_settings import OrganizationSettings
from .branch_protection_rule import BranchProtectionRule


@dataclass
class Repository(ModelObject):
    id: str = dataclass_field(metadata={"external_only": True})
    node_id: str = dataclass_field(metadata={"external_only": True})
    name: str = dataclass_field(metadata={"key": True})
    description: str
    homepage: str
    private: bool
    has_issues: bool
    has_projects: bool
    has_wiki: bool
    is_template: bool
    template_repository: str = dataclass_field(metadata={"read_only": True})
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
    branch_protection_rules: list[BranchProtectionRule] = dataclass_field(metadata={"model": True},
                                                                          default_factory=list)

    _security_properties: ClassVar[list[str]] = ["secret_scanning", "secret_scanning_push_protection"]

    _unavailable_fields_in_archived_repos: ClassVar[set[str]] = \
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
            "squash_merge_commit_title",
            "dependabot_alerts_enabled",
            "secret_scanning_push_protection"
         }

    def add_branch_protection_rule(self, rule: BranchProtectionRule) -> None:
        self.branch_protection_rules.append(rule)

    def set_branch_protection_rules(self, rules: list[BranchProtectionRule]) -> None:
        self.branch_protection_rules = rules

    def validate(self, context: ValidationContext, parent_object: object) -> None:
        org_settings: OrganizationSettings = parent_object.settings

        free_plan = org_settings.plan == "free"

        org_web_commit_signoff_required = org_settings.web_commit_signoff_required is True
        org_members_cannot_fork_private_repositories = org_settings.members_can_fork_private_repositories is False

        is_private = self.private is True
        is_public = self.private is False

        allow_forking = self.allow_forking is True
        disallow_forking = self.allow_forking is False

        if is_public and disallow_forking:
            context.add_failure(FailureType.WARNING,
                                f"public repo[name=\"{self.name}\"] has 'allow_forking' disabled "
                                f"which is not permitted.")

        has_wiki = self.has_wiki is True
        if is_private and has_wiki and free_plan:
            context.add_failure(FailureType.WARNING,
                                f"private repo[name=\"{self.name}\"] has 'has_wiki' enabled which"
                                f"requires at least GitHub Team billing, "
                                f"currently using \"{org_settings.plan}\" plan.")

        if is_private and org_members_cannot_fork_private_repositories and allow_forking:
            context.add_failure(FailureType.ERROR,
                                f"private repo[name=\"{self.name}\"] has 'allow_forking' enabled "
                                f"while the organization disables 'members_can_fork_private_repositories'.")

        repo_web_commit_signoff_not_required = self.web_commit_signoff_required is False
        if repo_web_commit_signoff_not_required and org_web_commit_signoff_required:
            context.add_failure(FailureType.ERROR,
                                f"repo[name=\"{self.name}\"] has 'web_commit_signoff_required' disabled while "
                                f"the organization requires it.")

        secret_scanning_disabled = self.secret_scanning == "disabled"
        secret_scanning_push_protection_enabled = self.secret_scanning_push_protection == "enabled"
        if secret_scanning_disabled and secret_scanning_push_protection_enabled:
            context.add_failure(FailureType.ERROR,
                                f"repo[name=\"{self.name}\"] has 'secret_scanning' disabled while "
                                f"'secret_scanning_push_protection' is enabled.")

        for bpr in self.branch_protection_rules:
            bpr.validate(context, self)

    def include_field_for_diff_computation(self, field: Field) -> bool:
        # private repos don't support security analysis.
        if self.private is True:
            if field.name in self._security_properties:
                return False

        if self.archived is True:
            if field.name in self._unavailable_fields_in_archived_repos:
                return False
            else:
                return True

        return True

    @classmethod
    def from_model(cls, data: dict[str, Any]) -> "Repository":
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}

        mapping.update(
            {
                "branch_protection_rules":
                    OptionalS("branch_protection_rules", default=[]) >>
                    Forall(lambda x: BranchProtectionRule.from_model(x))
            }
        )

        return cls(**bend(mapping, data))

    @classmethod
    def from_provider(cls, data: dict[str, Any]) -> "Repository":
        mapping = {k: OptionalS(k, default=UNSET) for k in map(lambda x: x.name, cls.all_fields())}

        mapping.update({
            "branch_protection_rules": K([]),

            "secret_scanning":
                OptionalS("security_and_analysis", "secret_scanning", "status", default=UNSET),
            "secret_scanning_push_protection":
                OptionalS("security_and_analysis", "secret_scanning_push_protection", "status", default=UNSET),

            "template_repository": OptionalS("template_repository", "full_name", default=None)
        })

        return cls(**bend(mapping, data))

    @classmethod
    def _to_provider(cls, data: dict[str, Any], provider: Union[Github, None] = None) -> dict[str, Any]:
        mapping = {field.name: S(field.name) for field in cls.provider_fields() if
                   not is_unset(data.get(field.name, UNSET))}

        # add mapping for items that GitHub expects in a nested structure.

        security_mapping = {}
        for security_prop in cls._security_properties:
            if security_prop in mapping:
                mapping.pop(security_prop)
            if security_prop in data:
                security_mapping[security_prop] = {"status": S(security_prop)}

        if len(security_mapping) > 0:
            mapping.update({"security_and_analysis": security_mapping})

        return bend(mapping, data)
