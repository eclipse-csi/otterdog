#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import re
from collections.abc import Mapping
from importlib.resources import files
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pretend import stub

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import FailureType, ModelObject, ValidationContext
from otterdog.models.organization_actions_policy import OrganizationActionsPolicy
from otterdog.models.repo_actions_policy import RepositoryActionsPolicy
from otterdog.utils import UNSET, jsonnet_evaluate_snippet

from . import ModelTest, evaluate_generated_jsonnet

ORG_ID = "my-org"
DEFAULTS = files("otterdog").joinpath("resources", "defaults", "otterdog-defaults.libsonnet")


class OrganizationActionsPolicyTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return OrganizationActionsPolicy.from_model_data(data)

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_org_actions_policy

    @property
    def model_data(self):
        raise NotImplementedError

    @property
    def provider_data(self):
        raise NotImplementedError


class RepositoryActionsPolicyTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return RepositoryActionsPolicy.from_model_data(data)

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_repo_actions_policy

    @property
    def model_data(self):
        raise NotImplementedError

    @property
    def provider_data(self):
        raise NotImplementedError


def evaluate(expression: str) -> dict[str, Any]:
    return jsonnet_evaluate_snippet(f"local orgs = import '{DEFAULTS}'; {expression}")


def repo_policy(extension: str = "") -> RepositoryActionsPolicy:
    return RepositoryActionsPolicy.from_model_data(evaluate(f"orgs.newRepoActionsPolicy('policy') {{ {extension} }}"))


def org_policy(extension: str = "") -> OrganizationActionsPolicy:
    return OrganizationActionsPolicy.from_model_data(
        evaluate(f"orgs.newOrgActionsPolicy('policy') {{ include_repo_names: ['~ALL'] }} {{ {extension} }}")
    )


def validate(
    policy: RepositoryActionsPolicy | OrganizationActionsPolicy,
    plan: str = "enterprise",
    repo_names: tuple[str, ...] = ("my-repo",),
) -> list[tuple[FailureType, str]]:
    context = ValidationContext(
        root_object=stub(settings=stub(plan=plan), repositories=[stub(name=x) for x in repo_names]),
        secret_resolver=stub(),
        template_dir="",
        org_members=set(),
        default_team_names=set(),
        exclude_teams_pattern=None,
    )
    parent = stub(get_model_header=lambda _=None: 'repository[name="my-repo"]', is_keyed=lambda: False)
    policy.validate(context, parent)
    return context.validation_failures


def _plain(message: str) -> str:
    """Returns a validation message without the markup of the header, e.g. '[bold]'."""
    return re.sub(r"\[(bold|/)\]", "", message).replace("\\[", "[")


def errors(policy: RepositoryActionsPolicy | OrganizationActionsPolicy, **kwargs: Any) -> list[str]:
    return [
        _plain(message) for failure_type, message in validate(policy, **kwargs) if failure_type == FailureType.ERROR
    ]


def warnings(policy: RepositoryActionsPolicy | OrganizationActionsPolicy, **kwargs: Any) -> list[str]:
    return [
        _plain(message) for failure_type, message in validate(policy, **kwargs) if failure_type == FailureType.WARNING
    ]


def github_provider() -> Any:
    async def get_user_id_and_type(login: str) -> tuple[int, str]:
        return (2, "Bot") if login.endswith("[bot]") else (1, "User")

    return stub(
        rest_api=stub(
            user=stub(get_user_id_and_type=AsyncMock(side_effect=get_user_id_and_type)),
            team=stub(get_team_ids=AsyncMock(return_value=(3, "team-node-id"))),
            app=stub(get_app_ids=AsyncMock(return_value=(4, "app-node-id"))),
        )
    )


def provider_policy(**overrides: Any) -> dict[str, Any]:
    return {
        "id": 7,
        "name": "policy",
        "target": "actions",
        "source_type": "Repository",
        "source": "my-org/my-repo",
        "enforcement": "active",
        "conditions": {"workflow_path": {"include": ["~ALL"], "exclude": []}},
        "rules": [],
        **overrides,
    }


# ---------------------------------------------------------------------------
# default configuration
# ---------------------------------------------------------------------------


def test_default_policy_targets_all_workflows_without_rules():
    policy = repo_policy()

    assert policy.enforcement == "active"
    assert policy.include_workflows == ["~ALL"]
    assert policy.exclude_workflows == []
    assert policy.allowed_actors is None
    assert policy.allowed_events is None


def test_default_org_policy_targets_no_repository():
    policy = OrganizationActionsPolicy.from_model_data(evaluate("orgs.newOrgActionsPolicy('policy')"))

    assert policy.include_repo_names == []
    assert policy.exclude_repo_names == []
    assert policy.protect_repo_names is False


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------


def test_valid_policy():
    policy = org_policy(
        """
        allowed_actors: ['@alice', '@my-org/admins', '#Maintain', '#42', 'my-app', '@dependabot[bot]'],
        allowed_events: ['push', 'pull_request_target'],
        """
    )

    assert validate(policy) == []


def test_unknown_enforcement_is_an_error():
    assert errors(repo_policy("enforcement: 'enforced', allowed_events: ['push']")) == [
        (
            "repo_actions_policy[name=\"policy\"] has 'enforcement' of value 'enforced', "
            "while only values ('active' | 'disabled' | 'evaluate') are allowed."
        )
    ]


@pytest.mark.parametrize("plan,expected_errors", [("enterprise", 0), ("team", 1), ("free", 1)])
def test_evaluate_requires_an_enterprise_plan(plan: str, expected_errors: int):
    policy = repo_policy("enforcement: 'evaluate', allowed_events: ['push']")

    assert len(errors(policy, plan=plan)) == expected_errors


@pytest.mark.parametrize(
    "include,exclude,message",
    [
        ("[]", "[]", "has empty 'include_workflows' and 'exclude_workflows'"),
        ("['~ALL', '.github/workflows/ci.yml']", "[]", "combining '~ALL' with other patterns"),
        ("[]", "['~ALL']", "has '~ALL' in 'exclude_workflows'"),
    ],
)
def test_invalid_workflow_patterns_are_errors(include: str, exclude: str, message: str):
    policy = repo_policy(f"include_workflows: {include}, exclude_workflows: {exclude}, allowed_events: ['push']")

    assert len(errors(policy)) == 1
    assert message in errors(policy)[0]


@pytest.mark.parametrize(
    "include,exclude",
    [
        ("['~ALL']", "[]"),
        ("['.github/workflows/release.yml', '.github/workflows/deploy-*.yml']", "[]"),
        ("[]", "['.github/workflows/ci.yml']"),
        ("['~ALL']", "['.github/workflows/ci.yml']"),
    ],
)
def test_valid_workflow_patterns(include: str, exclude: str):
    policy = repo_policy(f"include_workflows: {include}, exclude_workflows: {exclude}, allowed_events: ['push']")

    assert errors(policy) == []


@pytest.mark.parametrize(
    "actor,message",
    [
        ("alice@example.org", "an invalid allowed actor 'alice@example.org'"),
        ("@my-org/team/sub", "an invalid allowed actor '@my-org/team/sub'"),
        ("#Read", "allowed actor '#Read' with unknown role 'Read'"),
        ("Organization:1", "allowed actor 'Organization:1' with unknown type 'Organization'"),
    ],
)
def test_invalid_actors_are_errors(actor: str, message: str):
    policy = repo_policy(f"allowed_actors: ['{actor}']")

    assert len(errors(policy)) == 1
    assert message in errors(policy)[0]


def test_unknown_event_is_a_warning():
    assert warnings(repo_policy("allowed_events: ['push', 'pull_request_closed']")) == [
        (
            "repo_actions_policy[name=\"policy\"] has 'allowed_events' containing unknown event 'pull_request_closed', "
            "GitHub might reject it."
        )
    ]


@pytest.mark.parametrize("key", ["allowed_actors", "allowed_events"])
def test_empty_rule_is_a_warning(key: str):
    assert len(warnings(repo_policy(f"{key}: []"))) == 1


def test_policy_without_rules_is_a_warning():
    assert warnings(repo_policy()) == [
        (
            'repo_actions_policy[name="policy"] does not require any rule, '
            "set one of ('allowed_actors' | 'allowed_events')."
        )
    ]


def test_policy_with_rules_missing_from_the_configuration_is_not_reported():
    data = evaluate("orgs.newRepoActionsPolicy('policy') { allowed_events: ['push'] }")
    data.pop("allowed_actors")

    assert validate(RepositoryActionsPolicy.from_model_data(data)) == []


def test_org_policy_repo_patterns_matching_no_repository_are_warnings():
    policy = org_policy("include_repo_names: ['other-*'], exclude_repo_names: ['my-repo'], allowed_events: ['push']")

    assert warnings(policy) == [
        (
            "org_actions_policy[name=\"policy\"] has an 'include_repo_names' pattern 'other-*' "
            "that does not match any existing repository"
        ),
    ]


def test_org_policy_without_repositories_is_a_warning():
    policy = org_policy("include_repo_names: [], allowed_events: ['push']")

    assert len(warnings(policy)) == 1
    assert "has an empty 'include_repo_names'" in warnings(policy)[0]


# ---------------------------------------------------------------------------
# mapping from GitHub
# ---------------------------------------------------------------------------


def test_read_policy_from_github():
    data = provider_policy(
        conditions={"workflow_path": {"include": [".github/workflows/release.yml"], "exclude": ["ci.yml"]}},
        rules=[
            {
                "type": "restrict_actions_actors",
                "parameters": {
                    "allowed_actors": [
                        {"id": 1, "type": "User", "user_login": "alice"},
                        {"id": 2, "type": "Bot", "user_login": "dependabot[bot]"},
                        {"id": 3, "type": "Team", "team_slug": "my-org/admins"},
                        {"id": 4, "type": "App", "app_slug": "my-app"},
                        {"id": 2, "type": "RepositoryRole"},
                        {"id": 42, "type": "RepositoryRole"},
                        {"id": 5, "type": "EnterpriseTeam"},
                        {"id": 6, "type": "User"},
                    ]
                },
            },
            {"type": "restrict_action_events", "parameters": {"allowed_events": ["push"]}},
        ],
    )

    policy = RepositoryActionsPolicy.from_provider_data(ORG_ID, data)

    assert policy.id == 7
    assert policy.include_workflows == [".github/workflows/release.yml"]
    assert policy.exclude_workflows == ["ci.yml"]
    assert policy.allowed_actors == [
        "@alice",
        "@dependabot[bot]",
        "@my-org/admins",
        "my-app",
        "#Maintain",
        "#42",
        "EnterpriseTeam:5",
        "User:6",
    ]
    assert policy.allowed_events == ["push"]
    assert policy.unsupported_rules == []


def test_read_policy_without_workflow_condition_targets_all_workflows():
    policy = RepositoryActionsPolicy.from_provider_data(ORG_ID, provider_policy(conditions=None, rules=None))

    assert policy.include_workflows == ["~ALL"]
    assert policy.exclude_workflows == []
    assert policy.allowed_actors is None
    assert policy.allowed_events is None


def test_read_org_policy_repository_condition():
    data = provider_policy(
        source_type="Organization",
        conditions={
            "repository_name": {"include": ["~ALL"], "exclude": ["archive-*"], "protected": True},
            "workflow_path": {"include": ["~ALL"], "exclude": []},
        },
    )

    policy = OrganizationActionsPolicy.from_provider_data(ORG_ID, data)

    assert policy.include_repo_names == ["~ALL"]
    assert policy.exclude_repo_names == ["archive-*"]
    assert policy.protect_repo_names is True


def test_unsupported_rules_are_kept_but_not_compared():
    lockfile_rule = {"type": "require_lockfile", "parameters": {}}
    current = RepositoryActionsPolicy.from_provider_data(
        ORG_ID,
        provider_policy(
            rules=[{"type": "restrict_action_events", "parameters": {"allowed_events": ["push"]}}, lockfile_rule]
        ),
    )

    assert current.unsupported_rules == [lockfile_rule]
    assert repo_policy("allowed_events: ['push']").get_difference_from(current) == {}
    assert current.with_unsupported_rules({"rules": [{"type": "restrict_action_events"}]}) == {
        "rules": [{"type": "restrict_action_events"}, lockfile_rule]
    }
    # an update that does not provide the rules keeps them anyway
    assert current.with_unsupported_rules({"name": "policy"}) == {"name": "policy"}


# ---------------------------------------------------------------------------
# mapping to GitHub
# ---------------------------------------------------------------------------


async def test_write_policy_to_github():
    policy = repo_policy(
        """
        include_workflows: ['.github/workflows/release.yml'],
        allowed_actors: ['@alice', '@dependabot[bot]', '@my-org/admins', 'my-app', '#Write', '#42', 'EnterpriseTeam:5'],
        allowed_events: ['workflow_dispatch'],
        """
    )

    data = await policy.to_provider_data(ORG_ID, github_provider())

    assert data == {
        "name": "policy",
        "enforcement": "active",
        "conditions": {"workflow_path": {"include": [".github/workflows/release.yml"], "exclude": []}},
        "rules": [
            {
                "type": "restrict_actions_actors",
                "parameters": {
                    "allowed_actors": [
                        {"id": 1, "type": "User"},
                        {"id": 2, "type": "Bot"},
                        {"id": 3, "type": "Team"},
                        {"id": 4, "type": "App"},
                        {"id": 4, "type": "RepositoryRole"},
                        {"id": 42, "type": "RepositoryRole"},
                        {"id": 5, "type": "EnterpriseTeam"},
                    ]
                },
            },
            {"type": "restrict_action_events", "parameters": {"allowed_events": ["workflow_dispatch"]}},
        ],
    }


async def test_write_org_policy_to_github():
    policy = org_policy("exclude_repo_names: ['archive-*'], allowed_events: ['push']")

    data = await policy.to_provider_data(ORG_ID, github_provider())

    assert data["conditions"] == {
        "workflow_path": {"include": ["~ALL"], "exclude": []},
        "repository_name": {"include": ["~ALL"], "exclude": ["archive-*"], "protected": False},
    }


async def test_write_policy_without_rules_removes_them():
    data = await repo_policy().to_provider_data(ORG_ID, github_provider())

    assert data["rules"] == []


async def test_write_policy_with_rules_missing_from_the_configuration_keeps_them():
    data = evaluate("orgs.newRepoActionsPolicy('policy')")
    for key in ["allowed_actors", "allowed_events"]:
        data.pop(key)

    provider_data = await RepositoryActionsPolicy.from_model_data(data).to_provider_data(ORG_ID, github_provider())

    assert "rules" not in provider_data


def test_rules_missing_from_the_configuration_keep_their_current_values():
    data = evaluate("orgs.newRepoActionsPolicy('policy') { allowed_events: ['push'] }")
    data.pop("allowed_actors")
    current = RepositoryActionsPolicy.from_provider_data(
        ORG_ID,
        provider_policy(
            rules=[
                {
                    "type": "restrict_actions_actors",
                    "parameters": {"allowed_actors": [{"id": 4, "type": "RepositoryRole"}]},
                }
            ]
        ),
    )

    policy = RepositoryActionsPolicy.from_model_data(data).with_unset_rules_from(current)

    assert policy.allowed_actors == ["#Write"]
    assert policy.allowed_events == ["push"]


def test_roles_are_compared_by_name():
    current = RepositoryActionsPolicy.from_provider_data(
        ORG_ID,
        provider_policy(
            rules=[
                {
                    "type": "restrict_actions_actors",
                    "parameters": {"allowed_actors": [{"id": 4, "type": "RepositoryRole"}]},
                }
            ]
        ),
    )

    assert repo_policy("allowed_actors: ['#4']").get_difference_from(current) == {}


def test_changed_rule_is_a_difference():
    current = RepositoryActionsPolicy.from_provider_data(ORG_ID, provider_policy())

    diff = repo_policy("allowed_events: ['push']").get_difference_from(current)

    assert list(diff) == ["allowed_events"]
    assert diff["allowed_events"].from_value is None
    assert diff["allowed_events"].to_value == ["push"]


# ---------------------------------------------------------------------------
# generated jsonnet
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"include_workflows": [".github/workflows/release.yml"]},
        {"allowed_actors": ["@alice", "#Write"], "allowed_events": ["push"]},
        {"include_repo_names": ["~ALL"], "exclude_repo_names": ["archive-*"]},
    ],
)
def test_generated_jsonnet_evaluates_to_the_policy(overrides: dict[str, Any]):
    data = evaluate_generated_jsonnet(OrganizationActionsPolicy, "newOrgActionsPolicy('policy')", **overrides)

    for key, value in overrides.items():
        assert data[key] == value


def test_unset_fields_are_unset():
    policy = OrganizationActionsPolicy.from_model_data({"name": "policy"})

    assert policy.allowed_actors is UNSET
    assert policy.include_workflows is UNSET
