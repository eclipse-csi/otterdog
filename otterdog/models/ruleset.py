#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import abc
import dataclasses
import re
from typing import TYPE_CHECKING, Any, ClassVar, Self, TypeVar, cast

from jsonbender import F, Forall, If, K, OptionalS, S  # type: ignore

from otterdog.logging import get_logger
from otterdog.models import (
    EmbeddedModelObject,
    FailureType,
    ModelObject,
    PatchContext,
    ValidationContext,
)
from otterdog.utils import (
    UNSET,
    IndentingPrinter,
    associate_by_key,
    is_set_and_present,
    is_set_and_valid,
    is_unset,
    unwrap,
    write_patch_object_as_json,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from otterdog.jsonnet import JsonnetConfig
    from otterdog.providers.github import GitHubProvider

    from .github_organization import GitHubOrganization
    from .repository import Repository

RS = TypeVar("RS", bound="Ruleset")

_logger = get_logger(__name__)


@dataclasses.dataclass
class PullRequestSettings(EmbeddedModelObject):
    VALID_MERGE_METHODS: ClassVar[list[str]] = ["merge", "squash", "rebase"]

    required_approving_review_count: int
    dismisses_stale_reviews: bool = dataclasses.field(default=False)
    requires_code_owner_review: bool = dataclasses.field(default=False)
    requires_last_push_approval: bool = dataclasses.field(default=False)
    requires_review_thread_resolution: bool = dataclasses.field(default=False)
    # GitHub's default when the parameter is omitted: all three methods allowed.
    # As it is usually narrowed, it replaces its default in a patch instead of extending it.
    allowed_merge_methods: list[str] = dataclasses.field(
        default_factory=VALID_MERGE_METHODS.copy, metadata={"replace_on_patch": True}
    )

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        for key in self.keys(False):
            value = self.__getattribute__(key)
            if is_unset(value):
                context.add_failure(
                    FailureType.ERROR,
                    f"{parent_object.get_model_header()} has not set required parameter 'required_pull_request.{key}'.",
                )

        if is_set_and_valid(self.required_approving_review_count):
            if self.required_approving_review_count < 0 or self.required_approving_review_count > 10:
                context.add_failure(
                    FailureType.ERROR,
                    f"{parent_object.get_model_header()} has "
                    f"'required_pull_request.required_approving_review_count' of value "
                    f"'{self.required_approving_review_count}' while only integers in the range [0, 10] are allowed.",
                )

        if is_set_and_valid(self.allowed_merge_methods):
            if len(self.allowed_merge_methods) == 0:
                context.add_failure(
                    FailureType.ERROR,
                    f"{parent_object.get_model_header()} has an empty "
                    f"'required_pull_request.allowed_merge_methods' while at least one merge method must be allowed.",
                )

            for method in self.allowed_merge_methods:
                if method not in self.VALID_MERGE_METHODS:
                    context.add_failure(
                        FailureType.ERROR,
                        f"{parent_object.get_model_header()} has "
                        f"'required_pull_request.allowed_merge_methods' containing value '{method}' "
                        f"while only values in {self.VALID_MERGE_METHODS} are allowed.",
                    )

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_pull_request}"

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        mapping.update(
            {
                "required_approving_review_count": OptionalS("required_approving_review_count", default=UNSET),
                "dismisses_stale_reviews": OptionalS("dismiss_stale_reviews_on_push", default=UNSET),
                "requires_code_owner_review": OptionalS("require_code_owner_review", default=UNSET),
                "requires_last_push_approval": OptionalS("require_last_push_approval", default=UNSET),
                "requires_review_thread_resolution": OptionalS("required_review_thread_resolution", default=UNSET),
                "allowed_merge_methods": OptionalS("allowed_merge_methods", default=UNSET),
            }
        )

        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        mapping.update(
            {
                "dismiss_stale_reviews_on_push": S("dismisses_stale_reviews"),
                "require_code_owner_review": S("requires_code_owner_review"),
                "require_last_push_approval": S("requires_last_push_approval"),
                "required_review_thread_resolution": S("requires_review_thread_resolution"),
            }
        )

        for key in [
            "dismisses_stale_reviews",
            "requires_code_owner_review",
            "requires_last_push_approval",
            "requires_review_thread_resolution",
        ]:
            if key in mapping:
                mapping.pop(key)

        return mapping


@dataclasses.dataclass
class StatusCheckSettings(EmbeddedModelObject):
    do_not_enforce_on_create: bool
    strict: bool
    status_checks: list[str]

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        for key in ["strict", "status_checks"]:
            value = self.__getattribute__(key)
            if is_unset(value):
                context.add_failure(
                    FailureType.ERROR,
                    f"{parent_object.get_model_header()} has not set required parameter "
                    f"'required_status_checks.{key}'.",
                )

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_status_checks}"

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        def transform_status_check(status_check):
            if "app_slug" in status_check:
                return status_check["app_slug"] + ":" + status_check["context"]
            elif "integration_id" in status_check:
                return str(status_check["integration_id"]) + ":" + status_check["context"]
            else:
                return status_check["context"]

        mapping.update(
            {
                "do_not_enforce_on_create": OptionalS("do_not_enforce_on_create", default=UNSET),
                "strict": OptionalS("strict_required_status_checks_policy", default=UNSET),
                "status_checks": OptionalS("required_status_checks", default=[]) >> Forall(transform_status_check),
            }
        )

        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        status_checks = data.get("status_checks")

        # if an empty list of status checks is defined, do not set any checks at all.
        if status_checks is not None and len(status_checks) == 0:
            return {}

        if status_checks is not None:

            async def get_app_ids(checks) -> dict[str, str]:
                app_slugs = set()

                for check in checks:
                    if ":" in check:
                        app_slug, _context = re.split(":", check, maxsplit=1)

                        if app_slug != "any" and " " not in app_slug and not app_slug.isdigit():
                            app_slugs.add(app_slug)

                return await provider.get_app_ids(app_slugs)

            app_ids = await get_app_ids(status_checks)
        else:
            app_ids = {}

        def transform_status_check(status_check):
            if ":" in status_check:
                app_slug, context = re.split(":", status_check, maxsplit=1)

                if app_slug == "any":
                    app_slug = None
                elif " " in app_slug:
                    context = f"{app_slug}:{context}"
                    app_slug = None
            else:
                app_slug = None
                context = status_check

            if app_slug is None:
                return {"context": context}
            elif app_slug.isdigit():
                return {"integration_id": int(app_slug), "context": context}
            else:
                return {"integration_id": app_ids[app_slug], "context": context}

        mapping.update(
            {
                "strict_required_status_checks_policy": S("strict"),
                "required_status_checks": S("status_checks") >> Forall(transform_status_check),
            }
        )

        for key in [
            "strict",
            "status_checks",
        ]:
            if key in mapping:
                mapping.pop(key)

        return mapping


@dataclasses.dataclass
class MergeQueueSettings(EmbeddedModelObject):
    merge_method: str
    build_concurrency: int
    min_group_size: int
    max_group_size: int
    wait_time_for_minimum_group_size: int
    status_check_timeout: int
    requires_all_group_entries_to_pass_required_checks: bool

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        for key in self.keys(False):
            value = self.__getattribute__(key)
            if is_unset(value):
                context.add_failure(
                    FailureType.ERROR,
                    f"{parent_object.get_model_header()} has not set required parameter 'required_merge_queue.{key}'.",
                )

        if self.merge_method not in {"MERGE", "SQUASH", "REBASE"}:
            context.add_failure(
                FailureType.ERROR,
                f"{parent_object.get_model_header()} has 'required_merge_queue.merge_method' of value "
                f"'{self.merge_method}', only values ('MERGE' | 'SQUASH' | 'REBASE') are allowed.",
            )

        for key in [
            "build_concurrency",
            "min_group_size",
            "max_group_size",
            "wait_time_for_minimum_group_size",
            "status_check_timeout",
        ]:
            value = self.__getattribute__(key)
            if is_set_and_valid(value):
                if int(value) < 0:
                    context.add_failure(
                        FailureType.ERROR,
                        f"{parent_object.get_model_header()} has 'required_merge_queue.{key}' of value "
                        f"'{value}' while only non-negative integers are allowed.",
                    )

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_merge_queue}"

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        mapping.update(
            {
                "build_concurrency": S("max_entries_to_build"),
                "status_check_timeout": S("check_response_timeout_minutes"),
                "min_group_size": S("min_entries_to_merge"),
                "max_group_size": S("max_entries_to_merge"),
                "wait_time_for_minimum_group_size": S("min_entries_to_merge_wait_minutes"),
                "requires_all_group_entries_to_pass_required_checks": If(
                    S("grouping_strategy") == K("ALLGREEN"), K(True), K(False)
                ),
            }
        )

        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        mapping.update(
            {
                "max_entries_to_build": S("build_concurrency"),
                "check_response_timeout_minutes": S("status_check_timeout"),
                "min_entries_to_merge": S("min_group_size"),
                "max_entries_to_merge": S("max_group_size"),
                "min_entries_to_merge_wait_minutes": S("wait_time_for_minimum_group_size"),
                "grouping_strategy": If(
                    S("requires_all_group_entries_to_pass_required_checks") == K(True), K("ALLGREEN"), K("HEADGREEN")
                ),
            }
        )

        for key in [
            "build_concurrency",
            "status_check_timeout",
            "min_group_size",
            "max_group_size",
            "wait_time_for_minimum_group_size",
            "requires_all_group_entries_to_pass_required_checks",
        ]:
            if key in mapping:
                mapping.pop(key)

        return mapping


@dataclasses.dataclass(frozen=True)
class _EmbeddedModelOwner:
    """
    The owner of the embedded models of a ruleset when validating them, which name it in their messages with its
    header, e.g. 'repo_ruleset[name="main", repository=my-repo]'.
    """

    header: str

    def get_model_header(self) -> str:
        return self.header


def _quoted(values: list[str]) -> str:
    return " | ".join(f"'{x}'" for x in values)


@dataclasses.dataclass
class CopilotCodeReviewSettings(EmbeddedModelObject):
    review_on_push: bool = dataclasses.field(default=False)
    review_draft_pull_requests: bool = dataclasses.field(default=False)

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        # both parameters are optional booleans, there is nothing to validate
        pass

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_copilot_code_review}"


@dataclasses.dataclass
class PatternSettings(EmbeddedModelObject):
    """
    The parameters of a rule restricting the metadata of commits or the names of refs, e.g. 'commit_message_pattern'.
    """

    VALID_OPERATORS: ClassVar[list[str]] = ["starts_with", "ends_with", "contains", "regex"]

    operator: str
    pattern: str
    name: str = dataclasses.field(default="")
    negate: bool = dataclasses.field(default=False)

    def validate(self, context: ValidationContext, parent_object: Any, key: str = "pattern") -> None:
        for field in ["operator", "pattern"]:
            if is_unset(self.__getattribute__(field)):
                context.add_failure(
                    FailureType.ERROR,
                    f"{parent_object.get_model_header()} has not set required parameter '{key}.{field}'.",
                )

        if is_set_and_valid(self.operator) and self.operator not in self.VALID_OPERATORS:
            context.add_failure(
                FailureType.ERROR,
                f"{parent_object.get_model_header()} has '{key}.operator' of value '{self.operator}', "
                f"while only values ({_quoted(self.VALID_OPERATORS)}) are allowed.",
            )

        if is_set_and_valid(self.pattern) and len(self.pattern) == 0:
            context.add_failure(
                FailureType.ERROR,
                f"{parent_object.get_model_header()} has an empty '{key}.pattern'.",
            )

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_pattern}"

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = await super().get_mapping_to_provider(org_id, data, provider)

        # the name is optional, an empty name is not sent
        if not data.get("name") and "name" in mapping:
            mapping.pop("name")

        return mapping


@dataclasses.dataclass
class CodeScanningSettings(EmbeddedModelObject):
    """
    The parameters of the 'code_scanning' rule, a required tool is encoded as
    'tool:security_alerts_threshold:alerts_threshold', e.g. 'CodeQL:high_or_higher:errors'.
    """

    VALID_SECURITY_ALERTS_THRESHOLDS: ClassVar[list[str]] = [
        "none",
        "critical",
        "high_or_higher",
        "medium_or_higher",
        "all",
    ]
    VALID_ALERTS_THRESHOLDS: ClassVar[list[str]] = ["none", "errors", "errors_and_warnings", "all"]

    # written as a whole in a patch, so that a default list can be narrowed
    code_scanning_tools: list[str] = dataclasses.field(metadata={"replace_on_patch": True})

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        if is_unset(self.code_scanning_tools):
            context.add_failure(
                FailureType.ERROR,
                f"{parent_object.get_model_header()} has not set required parameter "
                f"'required_code_scanning.code_scanning_tools'.",
            )
            return

        if len(self.code_scanning_tools) == 0:
            context.add_failure(
                FailureType.ERROR,
                f"{parent_object.get_model_header()} has an empty 'required_code_scanning.code_scanning_tools' "
                f"while at least one tool must be required.",
            )

        for tool in self.code_scanning_tools:
            parts = tool.rsplit(":", 2)
            if len(parts) != 3 or len(parts[0]) == 0:
                context.add_failure(
                    FailureType.ERROR,
                    f"{parent_object.get_model_header()} has 'required_code_scanning.code_scanning_tools' "
                    f"containing value '{tool}' while only values of format "
                    f"'tool:security_alerts_threshold:alerts_threshold' are allowed.",
                )
                continue

            _, security_alerts_threshold, alerts_threshold = parts
            if security_alerts_threshold not in self.VALID_SECURITY_ALERTS_THRESHOLDS:
                context.add_failure(
                    FailureType.ERROR,
                    f"{parent_object.get_model_header()} has 'required_code_scanning.code_scanning_tools' "
                    f"containing value '{tool}' with a security alerts threshold of value "
                    f"'{security_alerts_threshold}', while only values "
                    f"({_quoted(self.VALID_SECURITY_ALERTS_THRESHOLDS)}) are allowed.",
                )

            if alerts_threshold not in self.VALID_ALERTS_THRESHOLDS:
                context.add_failure(
                    FailureType.ERROR,
                    f"{parent_object.get_model_header()} has 'required_code_scanning.code_scanning_tools' "
                    f"containing value '{tool}' with an alerts threshold of value '{alerts_threshold}', "
                    f"while only values ({_quoted(self.VALID_ALERTS_THRESHOLDS)}) are allowed.",
                )

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_code_scanning}"

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        def transform_tool(tool: dict[str, Any]) -> str:
            security_alerts_threshold = tool.get("security_alerts_threshold", "none")
            alerts_threshold = tool.get("alerts_threshold", "none")
            return f"{tool['tool']}:{security_alerts_threshold}:{alerts_threshold}"

        mapping.update(
            {
                "code_scanning_tools": OptionalS("code_scanning_tools", default=[]) >> Forall(transform_tool),
            }
        )

        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = await super().get_mapping_to_provider(org_id, data, provider)

        def transform_tool(tool: str) -> dict[str, Any]:
            name, security_alerts_threshold, alerts_threshold = tool.rsplit(":", 2)
            return {
                "tool": name,
                "security_alerts_threshold": security_alerts_threshold,
                "alerts_threshold": alerts_threshold,
            }

        if "code_scanning_tools" in mapping:
            mapping["code_scanning_tools"] = S("code_scanning_tools") >> Forall(transform_tool)

        return mapping


@dataclasses.dataclass
class CodeQualitySettings(EmbeddedModelObject):
    VALID_SEVERITIES: ClassVar[list[str]] = ["errors", "warnings", "notes", "all"]

    severity: str

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        if is_unset(self.severity):
            context.add_failure(
                FailureType.ERROR,
                f"{parent_object.get_model_header()} has not set required parameter 'required_code_quality.severity'.",
            )
        elif self.severity not in self.VALID_SEVERITIES:
            context.add_failure(
                FailureType.ERROR,
                f"{parent_object.get_model_header()} has 'required_code_quality.severity' of value "
                f"'{self.severity}', while only values ({_quoted(self.VALID_SEVERITIES)}) are allowed.",
            )

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_code_quality}"


@dataclasses.dataclass
class CodeCoverageSettings(EmbeddedModelObject):
    # GitHub does not enforce a threshold that is not set
    minimum_coverage: float | None = dataclasses.field(default=None)
    max_coverage_drop: float | None = dataclasses.field(default=None)

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        if self.minimum_coverage is None and self.max_coverage_drop is None:
            context.add_failure(
                FailureType.WARNING,
                f"{parent_object.get_model_header()} has neither 'required_code_coverage.minimum_coverage' nor "
                f"'required_code_coverage.max_coverage_drop' set, the rule has no effect.",
            )

        for key in ["minimum_coverage", "max_coverage_drop"]:
            value = self.__getattribute__(key)
            if is_set_and_valid(value) and not 0 <= value <= 100:
                context.add_failure(
                    FailureType.ERROR,
                    f"{parent_object.get_model_header()} has 'required_code_coverage.{key}' of value '{value}' "
                    f"while only percentages in the range [0, 100] are allowed.",
                )

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_code_coverage}"

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        return {key: S(key) for key in ["minimum_coverage", "max_coverage_drop"] if data.get(key) is not None}


@dataclasses.dataclass
class WorkflowsSettings(EmbeddedModelObject):
    """
    The parameters of the 'workflows' rule, a required workflow is encoded as 'repository:path[@ref]', the repository
    being its full name and the ref a branch, a tag or a commit sha,
    e.g. 'my-org/.github:.github/workflows/build.yml@refs/heads/main'.

    A repository whose name can not be resolved when loading a ruleset, e.g. because it was deleted, is shown by its
    id, which is not accepted in a configuration: the same workflow could otherwise be referenced in two ways.
    """

    _WORKFLOW_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?P<repository>[^/:@\s]+/[^/:@\s]+):(?P<path>[^@]+)(@(?P<ref>.+))?$"
    )
    _UNRESOLVED_WORKFLOW_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?P<repository_id>\d+):(?P<path>[^@]+)(@(?P<ref>.+))?$"
    )
    _SHA_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40}$")

    # written as a whole in a patch, so that a default list can be narrowed
    workflows: list[str] = dataclasses.field(metadata={"replace_on_patch": True})
    do_not_enforce_on_create: bool = dataclasses.field(default=False)

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        if is_unset(self.workflows):
            context.add_failure(
                FailureType.ERROR,
                f"{parent_object.get_model_header()} has not set required parameter 'required_workflows.workflows'.",
            )
            return

        if len(self.workflows) == 0:
            context.add_failure(
                FailureType.ERROR,
                f"{parent_object.get_model_header()} has an empty 'required_workflows.workflows' "
                f"while at least one workflow must be required.",
            )

        for workflow in self.workflows:
            if (unresolved := self._UNRESOLVED_WORKFLOW_PATTERN.match(workflow)) is not None:
                context.add_failure(
                    FailureType.ERROR,
                    f"{parent_object.get_model_header()} has 'required_workflows.workflows' containing value "
                    f"'{workflow}' whose repository with id '{unresolved.group('repository_id')}' could not be "
                    f"resolved, while a repository must be referenced by its full name 'owner/repository'.",
                )
            elif self._WORKFLOW_PATTERN.match(workflow) is None:
                context.add_failure(
                    FailureType.ERROR,
                    f"{parent_object.get_model_header()} has 'required_workflows.workflows' containing value "
                    f"'{workflow}' while only values of format 'owner/repository:path[@ref]' are allowed.",
                )

    def get_jsonnet_template_function(self, jsonnet_config: JsonnetConfig, extend: bool) -> str | None:
        return f"orgs.{jsonnet_config.create_workflows}"

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        def transform_workflow(workflow: dict[str, Any]) -> str:
            # the name of the repository is added when loading the ruleset, GitHub only provides its id
            repository = workflow.get("repository_name") or str(workflow["repository_id"])
            ref = workflow.get("ref") or workflow.get("sha")
            return f"{repository}:{workflow['path']}" + (f"@{ref}" if ref else "")

        mapping.update(
            {
                "workflows": OptionalS("workflows", default=[]) >> Forall(transform_workflow),
            }
        )

        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping = await super().get_mapping_to_provider(org_id, data, provider)

        if "workflows" not in mapping:
            return mapping

        # an unresolved repository keeps its id, e.g. in a rule kept from the current ruleset
        def match_workflow(workflow: str) -> re.Match[str]:
            return unwrap(cls._WORKFLOW_PATTERN.match(workflow) or cls._UNRESOLVED_WORKFLOW_PATTERN.match(workflow))

        matches = [match_workflow(workflow) for workflow in data["workflows"]]

        repository_ids: dict[str, int] = {}
        for repository in {match.group("repository") for match in matches if match.re is cls._WORKFLOW_PATTERN}:
            owner, name = repository.split("/")
            repository_ids[repository] = (await provider.rest_api.repo.get_repo_ids(owner, [name]))[0]

        def transform_workflow(workflow: str) -> dict[str, Any]:
            match = match_workflow(workflow)
            result: dict[str, Any] = {
                "repository_id": (
                    repository_ids[match.group("repository")]
                    if match.re is cls._WORKFLOW_PATTERN
                    else int(match.group("repository_id"))
                ),
                "path": match.group("path"),
            }

            ref = match.group("ref")
            if ref is not None:
                result["sha" if cls._SHA_PATTERN.match(ref) else "ref"] = ref

            return result

        mapping["workflows"] = S("workflows") >> Forall(transform_workflow)
        return mapping


def _embedded_model_from_model_data(model: type[EmbeddedModelObject]) -> Callable[[Any], Any]:
    def from_model_data(data: Any) -> Any:
        return data if data is None or is_unset(data) else model.from_model_data(data)

    return from_model_data


@dataclasses.dataclass(frozen=True)
class _EmbeddedRule:
    """
    A rule of a ruleset whose parameters are modelled as embedded model, which is null if the rule is not required.
    """

    key: str
    rule_type: str
    model: type[EmbeddedModelObject]
    # the property of the JsonnetConfig holding the default model data
    default_config: str


_PATTERN_RULES = [
    "commit_message_pattern",
    "commit_author_email_pattern",
    "committer_email_pattern",
    "branch_name_pattern",
    "tag_name_pattern",
]

_EMBEDDED_RULES = [
    _EmbeddedRule("required_pull_request", "pull_request", PullRequestSettings, "default_pull_request_config"),
    _EmbeddedRule("required_merge_queue", "merge_queue", MergeQueueSettings, "default_merge_queue_config"),
    _EmbeddedRule(
        "required_status_checks", "required_status_checks", StatusCheckSettings, "default_status_checks_config"
    ),
    _EmbeddedRule(
        "copilot_code_review",
        "copilot_code_review",
        CopilotCodeReviewSettings,
        "default_copilot_code_review_config",
    ),
    *(_EmbeddedRule(key, key, PatternSettings, "default_pattern_config") for key in _PATTERN_RULES),
    _EmbeddedRule("required_code_scanning", "code_scanning", CodeScanningSettings, "default_code_scanning_config"),
    _EmbeddedRule("required_code_quality", "code_quality", CodeQualitySettings, "default_code_quality_config"),
    _EmbeddedRule("required_code_coverage", "code_coverage", CodeCoverageSettings, "default_code_coverage_config"),
    _EmbeddedRule("required_workflows", "workflows", WorkflowsSettings, "default_workflows_config"),
]


@dataclasses.dataclass
class Ruleset(ModelObject, abc.ABC):
    """
    Represents a Ruleset.
    """

    id: int = dataclasses.field(metadata={"external_only": True})
    name: str = dataclasses.field(metadata={"key": True})
    node_id: str = dataclasses.field(metadata={"external_only": True})
    target: str
    enforcement: str

    bypass_actors: list[str]

    include_refs: list[str]
    exclude_refs: list[str]

    allows_creations: bool
    allows_deletions: bool
    allows_updates: bool
    allows_force_pushes: bool

    requires_commit_signatures: bool
    requires_linear_history: bool

    requires_deployments: bool
    required_deployment_environments: list[str]

    required_pull_request: PullRequestSettings | None = dataclasses.field(metadata={"embedded_model": True})
    required_status_checks: StatusCheckSettings | None = dataclasses.field(metadata={"embedded_model": True})
    required_merge_queue: MergeQueueSettings | None = dataclasses.field(metadata={"embedded_model": True})

    copilot_code_review: CopilotCodeReviewSettings | None = dataclasses.field(metadata={"embedded_model": True})

    commit_message_pattern: PatternSettings | None = dataclasses.field(metadata={"embedded_model": True})
    commit_author_email_pattern: PatternSettings | None = dataclasses.field(metadata={"embedded_model": True})
    committer_email_pattern: PatternSettings | None = dataclasses.field(metadata={"embedded_model": True})
    branch_name_pattern: PatternSettings | None = dataclasses.field(metadata={"embedded_model": True})
    tag_name_pattern: PatternSettings | None = dataclasses.field(metadata={"embedded_model": True})

    # the lists of push rules are written as a whole in a patch, so that a default list can be narrowed
    restricted_file_paths: list[str] = dataclasses.field(metadata={"replace_on_patch": True})
    restricted_file_paths_exceptions: list[str] = dataclasses.field(metadata={"replace_on_patch": True})
    max_file_path_length: int
    restricted_file_extensions: list[str] = dataclasses.field(metadata={"replace_on_patch": True})
    max_file_size: int
    max_file_size_exceptions: list[str] = dataclasses.field(metadata={"replace_on_patch": True})

    required_code_scanning: CodeScanningSettings | None = dataclasses.field(metadata={"embedded_model": True})
    required_code_quality: CodeQualitySettings | None = dataclasses.field(metadata={"embedded_model": True})
    required_code_coverage: CodeCoverageSettings | None = dataclasses.field(metadata={"embedded_model": True})
    requires_license_compliance_scanning: bool
    required_workflows: WorkflowsSettings | None = dataclasses.field(metadata={"embedded_model": True})

    _roles: ClassVar[dict[str, str]] = {"5": "RepositoryAdmin", "4": "Write", "2": "Maintain", "1": "OrganizationAdmin"}
    _inverted_roles: ClassVar[dict[str, str]] = {v: k for k, v in _roles.items()}

    # the rules that are only supported by rulesets with target 'push'
    _push_rules: ClassVar[list[str]] = [
        "restricted_file_paths",
        "max_file_path_length",
        "restricted_file_extensions",
        "max_file_size",
    ]

    # the rules that are not supported by rulesets with target 'push', the ones supported by otterdog before
    # the push rules only trigger a warning to keep configurations valid that define push rulesets with them
    _non_push_rules: ClassVar[list[str]] = [
        "copilot_code_review",
        *_PATTERN_RULES,
        "required_code_scanning",
        "required_code_quality",
        "required_code_coverage",
        "requires_license_compliance_scanning",
        "required_workflows",
    ]
    _legacy_non_push_rules: ClassVar[list[str]] = [
        "allows_creations",
        "allows_deletions",
        "allows_updates",
        "allows_force_pushes",
        "requires_commit_signatures",
        "requires_linear_history",
        "requires_deployments",
        "required_pull_request",
        "required_status_checks",
        "required_merge_queue",
    ]

    # the rules that GitHub only provides with a 'team' or 'enterprise' plan, resp. with an 'enterprise' plan,
    # they only trigger a warning as the documentation of GitHub is not explicit about all of them
    _team_plan_rules: ClassVar[list[str]] = [
        *_push_rules,
        "required_code_quality",
        "required_code_coverage",
    ]
    _enterprise_plan_rules: ClassVar[list[str]] = [
        *_PATTERN_RULES,
        "requires_license_compliance_scanning",
    ]

    # the keys modelling the rules of a ruleset
    _rule_keys: ClassVar[list[str]] = [
        "allows_creations",
        "allows_deletions",
        "allows_updates",
        "allows_force_pushes",
        "requires_commit_signatures",
        "requires_linear_history",
        "requires_license_compliance_scanning",
        "requires_deployments",
        *(rule.key for rule in _EMBEDDED_RULES),
        *_push_rules,
    ]

    # the keys modelling the parameters of rules, which are no rules on their own
    _rule_parameter_keys: ClassVar[list[str]] = [
        "required_deployment_environments",
        "restricted_file_paths_exceptions",
        "max_file_size_exceptions",
    ]

    # the push rules and their maximum values, 0 disables a rule
    _push_rule_limits: ClassVar[dict[str, int]] = {"max_file_path_length": 32767, "max_file_size": 100}

    # the maximum number of entries of the lists of push rules, and the maximum length of an entry
    _MAX_PUSH_RULE_ENTRIES: ClassVar[int] = 200

    def is_rule_configured(self, key: str) -> bool:
        """
        Returns whether the rule modelled by the given key is required by this ruleset.
        """
        value = self.__getattribute__(key)

        if not is_set_and_valid(value):
            return False
        elif key.startswith("allows_"):
            return value is False
        elif isinstance(value, bool):
            return value
        elif isinstance(value, int):
            return value > 0
        elif isinstance(value, list):
            return len(value) > 0
        else:
            return True

    def with_unset_rules_from(self, current_object: Ruleset) -> Self:
        """
        Returns a copy of this ruleset whose rules missing from the configuration, e.g. with a template predating
        them, keep the values of the current ruleset. GitHub replaces all the rules of a ruleset on update, these
        rules would otherwise be removed although they are not managed.
        """
        current_values = {
            key: current_object.__getattribute__(key)
            for key in [*self._rule_keys, *self._rule_parameter_keys]
            if is_unset(self.__getattribute__(key))
        }

        return dataclasses.replace(self, **current_values) if len(current_values) > 0 else self

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        org_settings = cast("GitHubOrganization", context.root_object).settings

        if is_set_and_valid(self.target):
            if self.target not in {"branch", "tag", "push"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'target' of value "
                    f"'{self.target}', while only values ('branch' | 'tag' | 'push') are allowed.",
                )

        enterprise_plan = org_settings.plan == "enterprise"
        if is_set_and_valid(self.enforcement):
            if self.enforcement not in {"active", "disabled", "evaluate"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'enforcement' of value '{self.enforcement}', "
                    f"while only values ('active' | 'disabled' | 'evaluate') are allowed.",
                )

            if enterprise_plan is False and self.enforcement == "evaluate":
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has 'enforcement' of value "
                    f"'{self.enforcement}' which is only available for an 'enterprise' plan.",
                )

        def valid_branch_condition_pattern(pattern: str) -> bool:
            return pattern.startswith("refs/heads/") or pattern == "~DEFAULT_BRANCH" or pattern == "~ALL"

        def valid_tag_condition_pattern(pattern: str) -> bool:
            return pattern.startswith("refs/tags/") or pattern == "~ALL"

        if is_set_and_valid(self.include_refs):
            for ref in self.include_refs:
                if (self.target == "branch" or self.target == "push") and not valid_branch_condition_pattern(ref):
                    context.add_failure(
                        FailureType.ERROR,
                        f"{self.get_model_header(parent_object)} has an invalid 'include_refs' pattern "
                        f"'{ref}', while only values ('refs/heads/*', '~DEFAULT_BRANCH', '~ALL') are allowed",
                    )
                elif self.target == "tag" and not valid_tag_condition_pattern(ref):
                    context.add_failure(
                        FailureType.ERROR,
                        f"{self.get_model_header(parent_object)} has an invalid 'include_refs' pattern "
                        f"'{ref}', while only values ('refs/tags/*', '~ALL') are allowed",
                    )

        if is_set_and_valid(self.exclude_refs):
            for ref in self.exclude_refs:
                if (self.target == "branch" or self.target == "push") and not valid_branch_condition_pattern(ref):
                    context.add_failure(
                        FailureType.ERROR,
                        f"{self.get_model_header(parent_object)} has an invalid 'exclude_refs' pattern "
                        f"'{ref}', while only values ('refs/heads/*', '~DEFAULT_BRANCH', '~ALL') are allowed",
                    )
                elif self.target == "tag" and not valid_tag_condition_pattern(ref):
                    context.add_failure(
                        FailureType.ERROR,
                        f"{self.get_model_header(parent_object)} has an invalid 'exclude_refs' pattern "
                        f"'{ref}', while only values ('refs/tags/*', '~ALL') are allowed",
                    )

        # if 'requires_deployments' is disabled, issue a warning if required_deployment_environments is non-empty.
        if (
            self.requires_deployments is False
            and is_set_and_valid(self.required_deployment_environments)
            and len(self.required_deployment_environments) > 0
        ):
            context.add_failure(
                FailureType.WARNING,
                f"{self.get_model_header(parent_object)} has "
                f"'requires_deployments' disabled but 'required_deployment_environments' is set to "
                f"'{self.required_deployment_environments}', setting will be ignored.",
            )

        if self.requires_deployments is True and len(self.required_deployment_environments) > 0:
            environments = cast("Repository", parent_object).environments

            environments_by_name = associate_by_key(environments, lambda x: x.name)
            for env_name in self.required_deployment_environments:
                if env_name not in environments_by_name:
                    context.add_failure(
                        FailureType.ERROR,
                        f"{self.get_model_header(parent_object)} requires deployment environment "
                        f"'{env_name}' which is not defined in the repository itself.",
                    )

        self._validate_push_rules(context, parent_object)
        self._validate_rule_targets(context, parent_object)
        self._validate_rule_plans(context, parent_object, org_settings.plan)

        # the messages of the embedded models name the ruleset, not only its repository or organization
        owner = _EmbeddedModelOwner(self.get_model_header(parent_object))

        for rule in _EMBEDDED_RULES:
            settings = self.__getattribute__(rule.key)
            if not is_set_and_present(settings):
                continue

            if isinstance(settings, PatternSettings):
                settings.validate(context, owner, rule.key)
            else:
                settings.validate(context, owner)

    def _report_configured_rules(
        self,
        context: ValidationContext,
        parent_object: Any,
        keys: list[str],
        failure_type: FailureType,
        message: Callable[[str], str],
    ) -> None:
        for key in keys:
            if self.is_rule_configured(key):
                context.add_failure(failure_type, f"{self.get_model_header(parent_object)} {message(key)}")

    def _validate_push_rules(self, context: ValidationContext, parent_object: Any) -> None:
        for key, maximum in self._push_rule_limits.items():
            value = self.__getattribute__(key)
            if is_set_and_valid(value) and not 0 <= value <= maximum:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has '{key}' of value '{value}' "
                    f"while only integers in the range [0, {maximum}] are allowed, 0 disabling the rule.",
                )

        for key in [
            "restricted_file_paths",
            "restricted_file_paths_exceptions",
            "restricted_file_extensions",
            "max_file_size_exceptions",
        ]:
            values = self.__getattribute__(key)
            if is_set_and_valid(values):
                self._validate_push_rule_entries(context, parent_object, key, values)

        for exceptions_key, rule_key in [
            ("restricted_file_paths_exceptions", "restricted_file_paths"),
            ("max_file_size_exceptions", "max_file_size"),
        ]:
            if self.is_rule_configured(exceptions_key) and not self.is_rule_configured(rule_key):
                context.add_failure(
                    FailureType.WARNING,
                    f"{self.get_model_header(parent_object)} has '{exceptions_key}' set to "
                    f"'{self.__getattribute__(exceptions_key)}' but '{rule_key}' is not set, setting will be ignored.",
                )

    def _validate_push_rule_entries(
        self, context: ValidationContext, parent_object: Any, key: str, values: list[str]
    ) -> None:
        if len(values) > self._MAX_PUSH_RULE_ENTRIES:
            context.add_failure(
                FailureType.ERROR,
                f"{self.get_model_header(parent_object)} has '{key}' with {len(values)} entries "
                f"while at most {self._MAX_PUSH_RULE_ENTRIES} entries are allowed.",
            )

        for value in values:
            if len(value) > self._MAX_PUSH_RULE_ENTRIES:
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has '{key}' containing value '{value}' "
                    f"which is longer than {self._MAX_PUSH_RULE_ENTRIES} characters.",
                )

    def _validate_rule_targets(self, context: ValidationContext, parent_object: Any) -> None:
        if not is_set_and_valid(self.target):
            return

        if self.target == "push":
            self._report_configured_rules(
                context,
                parent_object,
                self._non_push_rules,
                FailureType.ERROR,
                lambda key: f"has '{key}' set, while it is not supported by rulesets with target 'push'.",
            )
            self._report_configured_rules(
                context,
                parent_object,
                self._legacy_non_push_rules,
                FailureType.WARNING,
                lambda key: f"requires the rule of '{key}', while it is not supported by rulesets with target 'push'.",
            )
            # push rulesets apply to all refs of a repository
            self._report_configured_rules(
                context,
                parent_object,
                ["include_refs", "exclude_refs"],
                FailureType.WARNING,
                lambda key: f"has '{key}' set, which is ignored by rulesets with target 'push'.",
            )
        else:
            self._report_configured_rules(
                context,
                parent_object,
                self._push_rules,
                FailureType.ERROR,
                lambda key: f"has '{key}' set, while it is only supported by rulesets with target 'push'.",
            )

        for key, target in [("branch_name_pattern", "branch"), ("tag_name_pattern", "tag")]:
            if self.target != target and self.is_rule_configured(key):
                context.add_failure(
                    FailureType.ERROR,
                    f"{self.get_model_header(parent_object)} has '{key}' set, "
                    f"while it is only supported by rulesets with target '{target}'.",
                )

    def _validate_rule_plans(self, context: ValidationContext, parent_object: Any, plan: str) -> None:
        if not is_set_and_valid(plan):
            return

        if plan == "free":
            self._report_configured_rules(
                context,
                parent_object,
                self._team_plan_rules,
                FailureType.WARNING,
                lambda key: (
                    f"has '{key}' set, which requires at least GitHub Team billing, currently using '{plan}' plan."
                ),
            )

        if plan != "enterprise":
            self._report_configured_rules(
                context,
                parent_object,
                self._enterprise_plan_rules,
                FailureType.WARNING,
                lambda key: f"has '{key}' set, which requires an 'enterprise' plan, currently using '{plan}' plan.",
            )

    def include_field_for_diff_computation(self, field: dataclasses.Field) -> bool:
        if self.requires_deployments is False:
            if field.name in ["required_deployment_environments"]:
                return False

        if field.name in ["include_refs", "exclude_refs"] and self.target == "push":
            return False

        if field.name == "restricted_file_paths_exceptions" and not self.is_rule_configured("restricted_file_paths"):
            return False

        if field.name == "max_file_size_exceptions" and not self.is_rule_configured("max_file_size"):
            return False

        return True

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

    @classmethod
    def get_mapping_from_model(cls) -> dict[str, Any]:
        mapping = super().get_mapping_from_model()

        # a rule missing from the configuration, e.g. with a template predating it, is not managed, while null
        # disables it
        for rule in _EMBEDDED_RULES:
            mapping[rule.key] = OptionalS(rule.key, default=UNSET) >> F(_embedded_model_from_model_data(rule.model))

        return mapping

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        mapping.update(
            {
                # GitHub can return a disabled ruleset with conditions=null, leaving the nested ref paths absent.
                # Normalize absent/null filters to lists so live data can be compared with configured refs.
                "include_refs": OptionalS("conditions", default={})
                >> F(lambda conditions: ((conditions or {}).get("ref_name") or {}).get("include") or []),
                "exclude_refs": OptionalS("conditions", default={})
                >> F(lambda conditions: ((conditions or {}).get("ref_name") or {}).get("exclude") or []),
            }
        )

        rules = data.get("rules") or []

        def get_rule_parameters(rule_type: str) -> dict[str, Any] | None:
            for rule in rules:
                if rule["type"] == rule_type:
                    return rule.get("parameters") or {}

            return None

        def check_simple_rule(prop_key: str, rule_type: str, value_if_rule_is_present: bool) -> None:
            if any((_ := rule) for rule in rules if rule["type"] == rule_type):
                mapping[prop_key] = K(value_if_rule_is_present)
            else:
                mapping[prop_key] = K(not value_if_rule_is_present)

        check_simple_rule("allows_deletions", "deletion", False)
        check_simple_rule("allows_creations", "creation", False)
        check_simple_rule("allows_updates", "update", False)
        check_simple_rule("allows_force_pushes", "non_fast_forward", False)

        check_simple_rule("requires_commit_signatures", "required_signatures", True)
        check_simple_rule("requires_linear_history", "required_linear_history", True)
        check_simple_rule("requires_license_compliance_scanning", "license_compliance_scanning", True)

        # bypass actors
        if "bypass_actors" in data:
            bypass_actors = data["bypass_actors"]
            transformed_actors = []
            for actor in bypass_actors:
                actor_type = actor["actor_type"]

                if actor_type == "RepositoryRole":
                    role = cls._roles.get(str(actor["actor_id"]), None)
                    if role is None:
                        _logger.warning("fail to map repository role '%s', skipping", actor["actor_id"])
                        continue
                    transformed_actor = f"#{role}"
                elif actor_type == "OrganizationAdmin":
                    transformed_actor = "#OrganizationAdmin"
                elif actor_type == "Team":
                    team_slug = actor.get("team_slug")
                    if team_slug is None:
                        _logger.warning("fail to map team actor '%s', skipping", actor.get("actor_id", "unknown"))
                        continue
                    transformed_actor = f"@{team_slug}"
                elif actor_type == "User":
                    user_login = actor.get("user_login")
                    if user_login is None:
                        _logger.warning("fail to map user actor '%s', skipping", actor.get("actor_id", "unknown"))
                        continue
                    transformed_actor = f"@{user_login}"
                elif actor_type == "Integration":
                    app_slug = actor.get("app_slug")
                    if app_slug is None:
                        _logger.warning(
                            "fail to map integration actor '%s', skipping", actor.get("actor_id", "unknown")
                        )
                        continue
                    transformed_actor = app_slug
                else:
                    continue

                bypass_mode = actor.get("bypass_mode", "always")
                if bypass_mode != "always":
                    transformed_actor = f"{transformed_actor}:{bypass_mode}"

                transformed_actors.append(transformed_actor)

            mapping["bypass_actors"] = K(transformed_actors)

        else:
            mapping["bypass_actors"] = K([])

        # rules modelled as embedded models
        for rule in _EMBEDDED_RULES:
            parameters = get_rule_parameters(rule.rule_type)
            mapping[rule.key] = K(None if parameters is None else rule.model.from_provider_data(org_id, parameters))

        # required deployments
        if (parameters := get_rule_parameters("required_deployments")) is not None:
            mapping["requires_deployments"] = K(True)
            mapping["required_deployment_environments"] = K(parameters.get("required_deployment_environments", []))
        else:
            mapping["requires_deployments"] = K(False)
            mapping["required_deployment_environments"] = K([])

        # push rules
        file_path_restriction = get_rule_parameters("file_path_restriction") or {}
        mapping["restricted_file_paths"] = K(file_path_restriction.get("restricted_file_paths") or [])
        mapping["restricted_file_paths_exceptions"] = K(file_path_restriction.get("ignored_file_paths") or [])

        max_file_path_length = get_rule_parameters("max_file_path_length") or {}
        mapping["max_file_path_length"] = K(max_file_path_length.get("max_file_path_length") or 0)

        file_extension_restriction = get_rule_parameters("file_extension_restriction") or {}
        mapping["restricted_file_extensions"] = K(file_extension_restriction.get("restricted_file_extensions") or [])

        max_file_size = get_rule_parameters("max_file_size") or {}
        mapping["max_file_size"] = K(max_file_size.get("max_file_size") or 0)
        mapping["max_file_size_exceptions"] = K(max_file_size.get("ignored_file_paths") or [])

        return mapping

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping: dict[str, Any] = {
            field.name: S(field.name) for field in cls.provider_fields() if not is_unset(data.get(field.name, UNSET))
        }

        def pop_mapping(keys: list[str]) -> None:
            for key_to_pop in keys:
                if key_to_pop in mapping:
                    mapping.pop(key_to_pop)

        # include / excludes, push rulesets apply to all refs of a repository
        ref_names = {}
        if "include_refs" in data:
            mapping.pop("include_refs")
            ref_names["include"] = K(data["include_refs"])

        if "exclude_refs" in data:
            mapping.pop("exclude_refs")
            ref_names["exclude"] = K(data["exclude_refs"])

        if len(ref_names) > 0 and data.get("target") != "push":
            mapping["conditions"] = {"ref_name": ref_names}

        # bypass actors
        if "bypass_actors" in data:
            bypass_actors: list[str] = data["bypass_actors"]
            transformed_actors = []

            def extract_actor_and_bypass_mode(encoded_data: str) -> tuple[str, str]:
                if ":" in encoded_data:
                    a, m = re.split(":", encoded_data, maxsplit=1)
                else:
                    a = encoded_data
                    m = "always"

                return a, m

            for actor in bypass_actors:
                if actor.startswith("#"):
                    role, bypass_mode = extract_actor_and_bypass_mode(actor[1:])
                    actor_type = "RepositoryRole"
                    actor_id = cls._inverted_roles[role]
                    if actor_id == "1":
                        actor_type = "OrganizationAdmin"
                elif actor.startswith("@"):
                    actor_name, bypass_mode = extract_actor_and_bypass_mode(actor[1:])
                    if "/" in actor_name:
                        actor_type = "Team"
                        actor_id = (await provider.rest_api.team.get_team_ids(actor_name))[0]
                    else:
                        actor_type = "User"
                        actor_id = (await provider.rest_api.user.get_user_ids(actor_name))[0]
                else:
                    app, bypass_mode = extract_actor_and_bypass_mode(actor)
                    actor_type = "Integration"
                    actor_id = (await provider.rest_api.app.get_app_ids(app))[0]

                transformed_actors.append(
                    {"actor_id": K(int(actor_id)), "actor_type": K(actor_type), "bypass_mode": K(bypass_mode)}
                )

            mapping["bypass_actors"] = transformed_actors

        # rules
        rules: list[Any] = []

        def add_simple_rule(prop_key: str, rule_type: str, inverted: bool) -> None:
            if prop_key in data:
                mapping.pop(prop_key)
                prop_value = data[prop_key]

                if (inverted and not prop_value) or (not inverted and prop_value):
                    rules.append({"type": K(rule_type)})

        add_simple_rule("allows_deletions", "deletion", True)
        add_simple_rule("allows_creations", "creation", True)
        add_simple_rule("allows_updates", "update", True)
        add_simple_rule("allows_force_pushes", "non_fast_forward", True)

        add_simple_rule("requires_commit_signatures", "required_signatures", False)
        add_simple_rule("requires_linear_history", "required_linear_history", False)
        add_simple_rule("requires_license_compliance_scanning", "license_compliance_scanning", False)

        def add_parameter(prop_key: str, param_key: str, params: dict[str, Any]):
            if prop_key in data:
                params[param_key] = S(prop_key)

        # rules modelled as embedded models
        for embedded_rule in _EMBEDDED_RULES:
            if embedded_rule.key in data:
                mapping.pop(embedded_rule.key)
                settings = data[embedded_rule.key]
                if settings is not None:
                    parameters = await embedded_rule.model.dict_to_provider_data(org_id, settings, provider)
                    # an empty list of status checks is not required
                    if embedded_rule.rule_type == "required_status_checks" and len(parameters) == 0:
                        continue

                    rules.append({"type": K(embedded_rule.rule_type), "parameters": K(parameters)})

        # required deployments
        if "requires_deployments" in data:
            value = data["requires_deployments"]
            if value is True:
                rule = {"type": K("required_deployments")}
                deployment_parameters: dict[str, Any] = {}
                add_parameter(
                    "required_deployment_environments", "required_deployment_environments", deployment_parameters
                )
                rule["parameters"] = deployment_parameters
                rules.append(rule)

        pop_mapping(["requires_deployments", "required_deployment_environments"])

        # push rules, the exceptions of a rule are only sent if there are any
        def add_push_rule(rule_type: str, parameters: dict[str, Any]) -> None:
            rules.append(
                {
                    "type": K(rule_type),
                    "parameters": {key: K(value) for key, value in parameters.items() if value},
                }
            )

        if data.get("restricted_file_paths"):
            add_push_rule(
                "file_path_restriction",
                {
                    "restricted_file_paths": data["restricted_file_paths"],
                    "ignored_file_paths": data.get("restricted_file_paths_exceptions"),
                },
            )

        if data.get("max_file_path_length"):
            add_push_rule("max_file_path_length", {"max_file_path_length": data["max_file_path_length"]})

        if data.get("restricted_file_extensions"):
            add_push_rule(
                "file_extension_restriction", {"restricted_file_extensions": data["restricted_file_extensions"]}
            )

        if data.get("max_file_size"):
            add_push_rule(
                "max_file_size",
                {
                    "max_file_size": data["max_file_size"],
                    "ignored_file_paths": data.get("max_file_size_exceptions"),
                },
            )

        pop_mapping(
            [
                "restricted_file_paths",
                "restricted_file_paths_exceptions",
                "max_file_path_length",
                "restricted_file_extensions",
                "max_file_size",
                "max_file_size_exceptions",
            ]
        )

        # GitHub keeps the rules of a ruleset if an update does not provide them, they are provided even if there
        # are none to remove the last rule
        if len(rules) > 0 or any(key in data for key in cls._rule_keys):
            mapping["rules"] = rules

        return mapping

    def to_jsonnet(
        self,
        printer: IndentingPrinter,
        jsonnet_config: JsonnetConfig,
        context: PatchContext,
        extend: bool,
        default_object: ModelObject,
    ) -> None:
        patch = self.get_patch_to(default_object)

        template_function = self.get_jsonnet_template_function(jsonnet_config, False)

        if "name" in patch:
            patch.pop("name")

        printer.print(f"{unwrap(template_function)}('{self.name}')")

        for rule in _EMBEDDED_RULES:
            if rule.key in patch and patch.get(rule.key) is not None:
                patch.pop(rule.key)

        # the rules missing from the template, e.g. a template predating them, are written if they are configured
        embedded_keys = {rule.key for rule in _EMBEDDED_RULES}
        for key in [*self._rule_keys, *self._rule_parameter_keys]:
            if (
                key not in embedded_keys
                and is_unset(default_object.__getattribute__(key))
                and self.is_rule_configured(key)
            ):
                patch[key] = self.__getattribute__(key)

        write_patch_object_as_json(patch, printer, close_object=False, replace_keys=self.replace_on_patch_keys())

        for rule in _EMBEDDED_RULES:
            settings = self.__getattribute__(rule.key)
            if not is_set_and_present(settings):
                continue

            default_settings = default_object.__getattribute__(rule.key)
            if is_set_and_present(default_settings):
                embedded_extend = True
            elif (default_config := jsonnet_config.__getattribute__(rule.default_config)) is not None:
                default_settings = rule.model.from_model_data(default_config)
                embedded_extend = False
            else:
                # the template does not provide a function for the settings, e.g. a template predating the rule,
                # they are written as an object on their own
                printer.print(f"{rule.key}:")
                write_patch_object_as_json(
                    settings.to_model_dict(), printer, replace_keys=settings.replace_on_patch_keys()
                )
                continue

            embedded_patch = settings.get_patch_to(default_settings)
            # settings that are not required by default are written even if they equal their default values
            if len(embedded_patch) > 0 or embedded_extend is False:
                printer.print(f"{rule.key}{'+' if embedded_extend else ''}:")
                settings.to_jsonnet(printer, jsonnet_config, context, embedded_extend, default_settings)

        # close the object
        printer.level_down()
        printer.println("},")
