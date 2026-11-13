#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import abc
import dataclasses
import re
from typing import TYPE_CHECKING, Any, ClassVar, Self, cast

from jsonbender import F, K, OptionalS  # type: ignore

from otterdog.logging import get_logger
from otterdog.models import FailureType, ModelObject, ValidationContext
from otterdog.utils import UNSET, is_set_and_present, is_set_and_valid, is_unset

if TYPE_CHECKING:
    from otterdog.models.github_organization import GitHubOrganization
    from otterdog.providers.github import GitHubProvider

_logger = get_logger(__name__)

# the repository roles that can be selected as actors, same as for the bypass actors of rulesets
_ROLES = {"5": "RepositoryAdmin", "4": "Write", "2": "Maintain", "1": "OrganizationAdmin"}
_INVERTED_ROLES = {v: k for k, v in _ROLES.items()}

# the types of the actors that GitHub supports, an actor whose name can not be resolved is referenced by its type and
# id, e.g. 'EnterpriseTeam:42'
ACTOR_TYPES = (
    "User",
    "Bot",
    "Team",
    "BusinessTeam",
    "EnterpriseTeam",
    "IntegrationInstallation",
    "App",
    "RepositoryRole",
)

_ACTOR_PATTERN = re.compile(
    r"^(?:"
    r"(?P<account>@[^\s/:]+(?:/[^\s/:]+)?)"
    r"|(?P<role>#[\w-]+)"
    r"|(?P<app>[a-z0-9][a-z0-9-]*)"
    r"|(?P<type>[A-Za-z]+):(?P<id>\d+)"
    r")$"
)

# the events that GitHub lists for the rule restricting the events triggering workflows
EVENTS = (
    "branch_protection_rule",
    "check_run",
    "check_suite",
    "create",
    "delete",
    "deployment",
    "deployment_status",
    "discussion",
    "discussion_comment",
    "fork",
    "gollum",
    "image_version",
    "issue_comment",
    "issues",
    "label",
    "merge_group",
    "milestone",
    "page_build",
    "project",
    "project_card",
    "project_column",
    "public",
    "pull_request",
    "pull_request_review",
    "pull_request_review_comment",
    "pull_request_target",
    "push",
    "registry_package",
    "release",
    "repository_dispatch",
    "schedule",
    "status",
    "watch",
    "workflow_call",
    "workflow_dispatch",
    "workflow_run",
)

_ALL_WORKFLOWS = "~ALL"


def _validate_actor(actor: Any) -> str | None:
    """Returns the description of the problem of an allowed actor, if any."""
    match = _ACTOR_PATTERN.match(actor) if isinstance(actor, str) else None
    if match is None:
        return (
            f"an invalid allowed actor '{actor}', only users or bots ('@<login>'), teams ('@<org>/<team-slug>'), "
            f"roles ('#<role>'), apps ('<app-slug>') or actors referenced by their type and id ('<type>:<id>') "
            f"are supported."
        )

    role = match.group("role")
    if role is not None and role[1:] not in _INVERTED_ROLES and not role[1:].isdigit():
        return (
            f"allowed actor '{actor}' with unknown role '{role[1:]}', "
            f"only roles ({' | '.join(repr(x) for x in _INVERTED_ROLES)}) or the id of a custom role are supported."
        )

    actor_type = match.group("type")
    if actor_type is not None and actor_type not in ACTOR_TYPES:
        return (
            f"allowed actor '{actor}' with unknown type '{actor_type}', "
            f"only types ({' | '.join(repr(x) for x in ACTOR_TYPES)}) are supported."
        )

    return None


def _normalize_actors(actors: Any) -> Any:
    """
    Normalizes allowed actors to the representation they are read from GitHub with: roles that have a name are
    referenced by it.
    """
    if not isinstance(actors, list):
        return actors

    def normalize(actor: Any) -> Any:
        if isinstance(actor, str) and actor.startswith("#") and _validate_actor(actor) is None:
            role = actor[1:]
            return f"#{_ROLES.get(role, role)}"

        return actor

    return [normalize(actor) for actor in actors]


def _actor_from_provider(actor: dict[str, Any]) -> str:
    """
    Returns the reference of an allowed actor, its name is added to the data read from GitHub as 'user_login',
    'team_slug' or 'app_slug' if it could be resolved.
    """
    actor_type = actor.get("type")
    actor_id = actor.get("id")

    match actor_type:
        case "RepositoryRole":
            return f"#{_ROLES.get(str(actor_id), str(actor_id))}"
        case "User" | "Bot" if actor.get("user_login") is not None:
            return f"@{actor['user_login']}"
        case "Team" if actor.get("team_slug") is not None:
            return f"@{actor['team_slug']}"
        case "App" if actor.get("app_slug") is not None:
            return actor["app_slug"]
        case _:
            return f"{actor_type}:{actor_id}"


async def _actor_to_provider(actor: str, provider: GitHubProvider) -> dict[str, Any]:
    match = _ACTOR_PATTERN.match(actor)
    if match is None:
        raise ValueError(f"invalid allowed actor '{actor}'")

    if (actor_type := match.group("type")) is not None:
        return {"id": int(match.group("id")), "type": actor_type}

    if (role := match.group("role")) is not None:
        return {"id": int(_INVERTED_ROLES.get(role[1:], role[1:])), "type": "RepositoryRole"}

    if (account := match.group("account")) is not None:
        name = account[1:]
        if "/" in name:
            team_id, _ = await provider.rest_api.team.get_team_ids(name)
            return {"id": int(team_id), "type": "Team"}

        # bots, e.g. 'dependabot[bot]', are accounts of their own type
        user_id, user_type = await provider.rest_api.user.get_user_id_and_type(name)
        return {"id": int(user_id), "type": "Bot" if user_type == "Bot" else "User"}

    app_id, _ = await provider.rest_api.app.get_app_ids(actor)
    return {"id": int(app_id), "type": "App"}


def _workflows_from_provider(conditions: Any, key: str, default: list[str]) -> list[str]:
    """
    Returns the workflow patterns of a condition read from GitHub, which omits the workflow condition of a policy
    targeting all workflows if workflow targeting is not available, otherwise it reports it as '~ALL'.
    """
    workflow_path = (conditions or {}).get("workflow_path")
    if workflow_path is None:
        return list(default)

    return list(workflow_path.get(key) or [])


def _rule_parameters(rules: list[dict[str, Any]], rule_type: str) -> dict[str, Any] | None:
    """Returns the parameters of the rule of the given type, None if the policy does not require it."""
    for rule in rules:
        if rule.get("type") == rule_type:
            return rule.get("parameters") or {}

    return None


@dataclasses.dataclass
class ActionsPolicy(ModelObject, abc.ABC):
    """
    Represents an Actions policy, which protects the execution of workflows.

    The rules of a policy are modelled as properties that are null if the rule is not required. A rule whose type is
    not supported yet, e.g. as GitHub does not publish it in its API yet, is kept when the policy is updated.
    """

    id: int = dataclasses.field(metadata={"external_only": True})
    name: str = dataclasses.field(metadata={"key": True})
    enforcement: str

    # the workflows targeted by the policy, '~ALL' targets all workflows
    include_workflows: list[str] = dataclasses.field(metadata={"replace_on_patch": True})
    exclude_workflows: list[str] = dataclasses.field(metadata={"replace_on_patch": True})

    # rule 'restrict_actions_actors'
    allowed_actors: list[str] | None = dataclasses.field(metadata={"replace_on_patch": True})
    # rule 'restrict_action_events'
    allowed_events: list[str] | None = dataclasses.field(metadata={"replace_on_patch": True})

    # the rules of the policy whose type is not supported, as read from GitHub
    unsupported_rules: list[dict[str, Any]] = dataclasses.field(metadata={"external_only": True})

    # the keys modelling the rules of a policy and their rule types, a rule is added by adding its key here and
    # mapping its parameters in get_mapping_from_provider and get_mapping_to_provider
    _rule_types: ClassVar[dict[str, str]] = {
        "allowed_actors": "restrict_actions_actors",
        "allowed_events": "restrict_action_events",
    }

    # the keys of the conditions that GitHub updates together, e.g. the excluded workflows are reset if only the
    # included workflows are sent
    _condition_keys: ClassVar[list[tuple[str, ...]]] = [("include_workflows", "exclude_workflows")]

    def is_rule_configured(self, key: str) -> bool:
        """Returns whether the rule modelled by the given key is required by this policy."""
        return is_set_and_present(self.__getattribute__(key))

    def with_unset_values_from(self, current_object: ActionsPolicy) -> Self:
        """
        Returns a copy of this policy whose values missing from the configuration, e.g. with a template predating
        them, keep the values of the current policy, as GitHub replaces them on update although they are not managed:

        - the rules, GitHub replaces all the rules of a policy
        - the keys of a condition, if another key of the condition is configured, e.g. the excluded workflows if only
          the included workflows are configured
        """
        keys = [key for key in self._rule_types if is_unset(self.__getattribute__(key))]

        for condition_keys in self._condition_keys:
            unset_keys = [key for key in condition_keys if is_unset(self.__getattribute__(key))]
            if len(unset_keys) < len(condition_keys):
                keys.extend(unset_keys)

        current_values = {
            key: current_object.__getattribute__(key)
            for key in keys
            if not is_unset(current_object.__getattribute__(key))
        }

        return dataclasses.replace(self, **current_values) if len(current_values) > 0 else self

    def with_unsupported_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Returns the data of an update of this current policy that keeps its settings not supported by otterdog, which
        GitHub would otherwise replace: the rules of an unsupported type, as GitHub replaces all the rules of a policy.
        """
        if "rules" not in data or not is_set_and_present(self.unsupported_rules) or len(self.unsupported_rules) == 0:
            return data

        return {**data, "rules": [*data["rules"], *self.unsupported_rules]}

    def validate(self, context: ValidationContext, parent_object: Any) -> None:
        header = self.get_model_header(parent_object)

        if is_set_and_valid(self.name) and len(self.name.strip()) == 0:
            context.add_failure(FailureType.ERROR, f"{header} has an empty 'name'.")

        if is_set_and_valid(self.enforcement):
            if self.enforcement not in {"active", "disabled", "evaluate"}:
                context.add_failure(
                    FailureType.ERROR,
                    f"{header} has 'enforcement' of value '{self.enforcement}', "
                    f"while only values ('active' | 'disabled' | 'evaluate') are allowed.",
                )

            plan = cast("GitHubOrganization", context.root_object).settings.plan
            if self.enforcement == "evaluate" and is_set_and_valid(plan) and plan != "enterprise":
                context.add_failure(
                    FailureType.ERROR,
                    f"{header} has 'enforcement' of value '{self.enforcement}' "
                    f"which is only available for an 'enterprise' plan.",
                )

        self._validate_workflows(context, header)
        self._validate_rules(context, header)

    def _validate_workflows(self, context: ValidationContext, header: str) -> None:
        include_workflows = self.include_workflows if is_set_and_valid(self.include_workflows) else []
        exclude_workflows = self.exclude_workflows if is_set_and_valid(self.exclude_workflows) else []

        if (
            is_set_and_valid(self.include_workflows)
            and is_set_and_valid(self.exclude_workflows)
            and len(include_workflows) == 0
            and len(exclude_workflows) == 0
        ):
            context.add_failure(
                FailureType.ERROR,
                f"{header} has empty 'include_workflows' and 'exclude_workflows', while at least one pattern "
                f"is required, use '{_ALL_WORKFLOWS}' to target all workflows.",
            )

        if _ALL_WORKFLOWS in include_workflows and len(include_workflows) > 1:
            context.add_failure(
                FailureType.ERROR,
                f"{header} has 'include_workflows' combining '{_ALL_WORKFLOWS}' with other patterns, "
                f"while '{_ALL_WORKFLOWS}' must be used on its own.",
            )

        if _ALL_WORKFLOWS in exclude_workflows:
            context.add_failure(
                FailureType.ERROR,
                f"{header} has '{_ALL_WORKFLOWS}' in 'exclude_workflows', while it is only allowed in "
                f"'include_workflows'.",
            )

    def _validate_rules(self, context: ValidationContext, header: str) -> None:
        if is_set_and_present(self.allowed_actors):
            self._validate_actors(context, header, self.allowed_actors)

        if is_set_and_present(self.allowed_events):
            self._validate_events(context, header, self.allowed_events)

        rule_values = [self.__getattribute__(key) for key in self._rule_types]
        if all(not is_unset(x) for x in rule_values) and not any(self.is_rule_configured(x) for x in self._rule_types):
            context.add_failure(
                FailureType.WARNING,
                f"{header} does not require any rule, set one of ({' | '.join(repr(x) for x in self._rule_types)}).",
            )

    @staticmethod
    def _validate_actors(context: ValidationContext, header: str, actors: list[str]) -> None:
        for actor in actors:
            if (error := _validate_actor(actor)) is not None:
                context.add_failure(FailureType.ERROR, f"{header} has {error}")

        if len(actors) == 0:
            context.add_failure(
                FailureType.WARNING,
                f"{header} has an empty 'allowed_actors', no actor is allowed to run the targeted workflows.",
            )

    @staticmethod
    def _validate_events(context: ValidationContext, header: str, events: list[str]) -> None:
        for event in events:
            if event not in EVENTS:
                context.add_failure(
                    FailureType.WARNING,
                    f"{header} has 'allowed_events' containing unknown event '{event}', GitHub might reject it.",
                )

        if len(events) == 0:
            context.add_failure(
                FailureType.WARNING,
                f"{header} has an empty 'allowed_events', no event is allowed to trigger the targeted workflows.",
            )

    def include_field_for_patch_computation(self, field: dataclasses.Field) -> bool:
        return True

    @classmethod
    def get_mapping_from_model(cls) -> dict[str, Any]:
        mapping = super().get_mapping_from_model()

        # actors are compared in the representation they are read from GitHub with
        mapping["allowed_actors"] = OptionalS("allowed_actors", default=UNSET) >> F(_normalize_actors)

        return mapping

    @classmethod
    def get_mapping_from_provider(cls, org_id: str, data: dict[str, Any]) -> dict[str, Any]:
        mapping = super().get_mapping_from_provider(org_id, data)

        conditions = data.get("conditions")
        mapping.update(
            {
                "include_workflows": K(_workflows_from_provider(conditions, "include", [_ALL_WORKFLOWS])),
                "exclude_workflows": K(_workflows_from_provider(conditions, "exclude", [])),
            }
        )

        mapping.update({key: K(value) for key, value in cls._rules_from_provider(data).items()})

        return mapping

    @classmethod
    def _rules_from_provider(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Returns the values of the keys modelling the rules of a policy read from GitHub, and its unsupported rules."""
        rules = data.get("rules") or []

        actors_parameters = _rule_parameters(rules, cls._rule_types["allowed_actors"])
        events_parameters = _rule_parameters(rules, cls._rule_types["allowed_events"])

        supported_rule_types = set(cls._rule_types.values())
        unsupported_rules = [rule for rule in rules if rule.get("type") not in supported_rule_types]
        for rule in unsupported_rules:
            _logger.debug(
                "actions policy '%s' has a rule of unsupported type '%s', it is kept on update",
                data.get("name"),
                rule.get("type"),
            )

        return {
            "allowed_actors": None
            if actors_parameters is None
            else [_actor_from_provider(actor) for actor in actors_parameters.get("allowed_actors") or []],
            "allowed_events": None
            if events_parameters is None
            else list(events_parameters.get("allowed_events") or []),
            "unsupported_rules": unsupported_rules,
        }

    @classmethod
    async def get_mapping_to_provider(
        cls, org_id: str, data: dict[str, Any], provider: GitHubProvider
    ) -> dict[str, Any]:
        mapping: dict[str, Any] = {
            field.name: K(data[field.name])
            for field in cls.provider_fields()
            if not is_unset(data.get(field.name, UNSET))
        }

        # the workflow condition, GitHub keeps the current one if it is omitted on update, a key missing from the
        # configuration is set to its current value before an update, see with_unset_values_from
        workflow_path = {}
        for key, condition_key in [("include_workflows", "include"), ("exclude_workflows", "exclude")]:
            if key in mapping:
                mapping.pop(key)
                workflow_path[condition_key] = K(data[key])

        if len(workflow_path) > 0:
            workflow_path.setdefault("include", K([]))
            workflow_path.setdefault("exclude", K([]))
            mapping["conditions"] = {"workflow_path": workflow_path}

        # the rules, GitHub keeps the rules of a policy if an update does not provide them, they are provided even if
        # there are none to remove the last rule
        rules: list[Any] = []

        for key in cls._rule_types:
            mapping.pop(key, None)

        if (actors := data.get("allowed_actors")) is not None and not is_unset(actors):
            rules.append(
                {
                    "type": K(cls._rule_types["allowed_actors"]),
                    "parameters": {
                        "allowed_actors": K([await _actor_to_provider(actor, provider) for actor in actors]),
                    },
                }
            )

        if (events := data.get("allowed_events")) is not None and not is_unset(events):
            rules.append(
                {
                    "type": K(cls._rule_types["allowed_events"]),
                    "parameters": {"allowed_events": K(list(events))},
                }
            )

        if any(not is_unset(data.get(key, UNSET)) for key in cls._rule_types):
            mapping["rules"] = rules

        return mapping
