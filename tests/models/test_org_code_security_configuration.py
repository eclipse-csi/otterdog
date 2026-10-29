#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import dataclasses
from collections.abc import Mapping
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pretend import stub

from otterdog.jsonnet import JsonnetConfig
from otterdog.models import CostPolicy, FailureType, LivePatch, LivePatchContext, ModelObject, ValidationContext
from otterdog.models.github_organization import (
    GitHubOrganization,
    _add_code_security_configurations,
    _enrich_team_bypass_reviewers,
    _load_code_security_configuration_attachments,
)
from otterdog.models.organization_code_security_configuration import (
    CodeSecurityConfigurationPlan,
    OrganizationCodeSecurityConfiguration,
)
from otterdog.models.repository import Repository
from otterdog.utils import UNSET, Change, jsonnet_evaluate_snippet, unwrap

from . import _EXAMPLE_CONFIG, ModelTest


def default_configuration(**overrides: Any) -> OrganizationCodeSecurityConfiguration:
    data = jsonnet_evaluate_snippet(f"(import '{_EXAMPLE_CONFIG}').newOrgCodeSecurityConfiguration('default')")
    data.update(overrides)
    return OrganizationCodeSecurityConfiguration.from_model_data(data)


def validation_context() -> ValidationContext:
    return ValidationContext(
        root_object=None,
        secret_resolver=stub(),
        template_dir="",
        org_members=set(),
        default_team_names=set(),
        exclude_teams_pattern=None,
    )


def validate(configuration: OrganizationCodeSecurityConfiguration) -> list[tuple[FailureType, str]]:
    context = validation_context()
    configuration.validate(context, None)
    return context.validation_failures


def failures_of_type(failures: list[tuple[FailureType, str]], failure_type: FailureType) -> list[str]:
    return [message for t, message in failures if t == failure_type]


class OrganizationCodeSecurityConfigurationTest(ModelTest):
    def create_model(self, data: Mapping[str, Any]) -> ModelObject:
        return OrganizationCodeSecurityConfiguration.from_model_data(data)

    @property
    def template_function(self) -> str:
        return JsonnetConfig.create_org_code_security_configuration

    @property
    def model_data(self):
        return self.load_json_resource("otterdog-org-code-security-configuration.json")

    @property
    def provider_data(self):
        return self.load_json_resource("github-org-code-security-configuration.json")

    @property
    def provider(self):
        provider = MagicMock()
        provider.rest_api.team.get_team_ids = AsyncMock(return_value=(1234, "T_1234"))
        return provider

    def test_load_from_model(self):
        configuration = OrganizationCodeSecurityConfiguration.from_model_data(self.model_data)

        assert configuration.id is UNSET
        assert configuration.name == "my-config"
        assert configuration.description == "My code security configuration"
        assert configuration.code_security == "disabled"
        assert configuration.secret_protection == "enabled"
        assert configuration.dependency_graph_autosubmit_action_labeled_runners is True
        assert configuration.dependabot_reachability is None
        assert configuration.code_scanning_default_setup_runner_type == "labeled"
        assert configuration.code_scanning_default_setup_runner_label == "code-scanning"
        assert configuration.code_scanning_allow_advanced is False
        assert configuration.secret_scanning_delegated_bypass_reviewers == [
            "@OtterdogTest/security-team",
            "#RepositoryAdmin",
            "#4711:exempt",
        ]
        assert configuration.enforcement == "enforced"
        assert configuration.default_for_new_repos == "private_and_internal"

    def test_load_from_provider(self):
        configuration = OrganizationCodeSecurityConfiguration.from_provider_data(self.org_id, self.provider_data)

        assert configuration.id == 42

        # the provider data represents the same configuration as the model data
        expected = OrganizationCodeSecurityConfiguration.from_model_data(self.model_data)
        assert expected.get_difference_from(configuration) == {}

        # GitHub does not report settings an organization has no access to, they are not compared
        assert configuration.dependabot_reachability is UNSET

    def test_load_from_provider_without_options(self):
        data = {
            "id": 1,
            "name": "minimal",
            "description": None,
            "advanced_security": "disabled",
            "code_scanning_default_setup_options": None,
        }

        configuration = OrganizationCodeSecurityConfiguration.from_provider_data(self.org_id, data)

        assert configuration.description == ""
        assert configuration.dependency_graph_autosubmit_action_labeled_runners is None
        assert configuration.code_scanning_default_setup_runner_type is None
        assert configuration.code_scanning_default_setup_runner_label is None
        assert configuration.code_scanning_allow_advanced is None
        assert configuration.secret_scanning_delegated_bypass_reviewers == []
        assert configuration.default_for_new_repos is UNSET

    async def test_to_provider(self):
        configuration = OrganizationCodeSecurityConfiguration.from_model_data(self.model_data)

        provider_data = await configuration.to_provider_data(self.org_id, self.provider)

        assert "id" not in provider_data
        assert provider_data["name"] == "my-config"
        # GitHub rejects 'advanced_security' along with the individual products
        assert "advanced_security" not in provider_data
        assert provider_data["code_security"] == "disabled"
        assert provider_data["secret_protection"] == "enabled"
        assert provider_data["dependency_graph_autosubmit_action_options"] == {"labeled_runners": True}
        assert provider_data["code_scanning_options"] == {"allow_advanced": False}
        assert provider_data["code_scanning_default_setup_options"] == {
            "runner_type": "labeled",
            "runner_label": "code-scanning",
        }
        assert provider_data["secret_scanning_delegated_bypass_options"] == {
            "reviewers": [
                {"reviewer_id": 1234, "reviewer_type": "TEAM", "mode": "ALWAYS"},
                {"reviewer_id": 5, "reviewer_type": "ROLE", "mode": "ALWAYS"},
                {"reviewer_id": 4711, "reviewer_type": "ROLE", "mode": "EXEMPT"},
            ]
        }
        assert provider_data["enforcement"] == "enforced"

        # settings that are not managed and the default for new repos are not part of the configuration
        assert "dependabot_reachability" not in provider_data
        assert "default_for_new_repos" not in provider_data
        for key in (
            "dependency_graph_autosubmit_action_labeled_runners",
            "code_scanning_allow_advanced",
            "code_scanning_default_setup_runner_type",
            "code_scanning_default_setup_runner_label",
            "secret_scanning_delegated_bypass_reviewers",
        ):
            assert key not in provider_data

    async def test_to_provider_of_default_configuration(self):
        provider_data = await default_configuration().to_provider_data(self.org_id, self.provider)

        # 'advanced_security' is available on all plans, unlike the individual products
        assert provider_data["advanced_security"] == "disabled"
        assert "code_security" not in provider_data
        assert "secret_protection" not in provider_data

        for key in OrganizationCodeSecurityConfiguration._optional_properties:
            assert key not in provider_data

        for key in (
            "dependency_graph_autosubmit_action_options",
            "code_scanning_options",
            "code_scanning_default_setup_options",
            "secret_scanning_delegated_bypass_options",
        ):
            assert key not in provider_data

    async def test_to_provider_omits_runner_label_of_standard_runners(self):
        configuration = default_configuration(
            code_scanning_default_setup_runner_type="standard", code_scanning_default_setup_runner_label="ignored"
        )

        provider_data = await configuration.to_provider_data(self.org_id, self.provider)

        assert provider_data["code_scanning_default_setup_options"] == {"runner_type": "standard"}

    def test_patch(self):
        current = OrganizationCodeSecurityConfiguration.from_provider_data(self.org_id, self.provider_data)
        expected = OrganizationCodeSecurityConfiguration.from_model_data(
            {**self.model_data, "default_for_new_repos": "all", "secret_scanning_validity_checks": "disabled"}
        )

        diff = expected.get_difference_from(current)

        assert diff == {
            "default_for_new_repos": Change("private_and_internal", "all"),
            "secret_scanning_validity_checks": Change("enabled", "disabled"),
        }

    def test_optional_properties_set_to_none_are_not_managed(self):
        current = OrganizationCodeSecurityConfiguration.from_provider_data(self.org_id, self.provider_data)
        expected = OrganizationCodeSecurityConfiguration.from_model_data(
            {**self.model_data, **dict.fromkeys(OrganizationCodeSecurityConfiguration._optional_properties)}
        )

        assert expected.get_difference_from(current) == {}

    def test_default_configuration_is_valid(self):
        assert validate(default_configuration()) == []

    def test_example_configuration_is_valid(self):
        configuration = OrganizationCodeSecurityConfiguration.from_model_data(self.model_data)

        assert validate(configuration) == []


@pytest.mark.parametrize(
    ("advanced_security", "code_security", "secret_protection"),
    [
        ("enabled", "enabled", "enabled"),
        ("disabled", "disabled", "disabled"),
        ("code_security", "enabled", "disabled"),
        ("secret_protection", "disabled", "enabled"),
    ],
)
def test_advanced_security_is_split_into_products(advanced_security, code_security, secret_protection):
    # GitHub reports the individual products as null
    configuration = OrganizationCodeSecurityConfiguration.from_provider_data(
        "OtterdogTest",
        {
            "id": 1,
            "name": "config",
            "advanced_security": advanced_security,
            "code_security": None,
            "secret_protection": None,
        },
    )

    assert configuration.code_security == code_security
    assert configuration.secret_protection == secret_protection


@pytest.mark.parametrize(
    ("code_security", "secret_protection", "advanced_security"),
    [
        ("enabled", "enabled", "enabled"),
        ("disabled", "disabled", "disabled"),
        ("enabled", "disabled", None),
        ("disabled", "enabled", None),
    ],
)
async def test_advanced_security_is_sent_instead_of_the_same_products(
    code_security, secret_protection, advanced_security
):
    configuration = default_configuration(code_security=code_security, secret_protection=secret_protection)

    provider_data = await configuration.to_provider_data("OtterdogTest", MagicMock())

    # GitHub rejects 'advanced_security' along with the individual products, which are only available on an
    # unbundled Advanced Security plan
    if advanced_security is not None:
        assert provider_data["advanced_security"] == advanced_security
        assert "code_security" not in provider_data
        assert "secret_protection" not in provider_data
    else:
        assert "advanced_security" not in provider_data
        assert provider_data["code_security"] == code_security
        assert provider_data["secret_protection"] == secret_protection


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("code_security", "not_set"),
        ("secret_protection", "code_security"),
        ("dependency_graph", "on"),
        ("secret_scanning_generic_secrets", "true"),
        ("enforcement", "enterprise_enforced"),
        ("default_for_new_repos", "private"),
        ("code_scanning_default_setup_runner_type", "large"),
    ],
)
def test_validate_invalid_values(key, value):
    errors = failures_of_type(validate(default_configuration(**{key: value})), FailureType.ERROR)

    assert len(errors) == 1
    assert f"has '{key}' of value '{value}'" in errors[0]


def test_validate_description_length():
    errors = failures_of_type(validate(default_configuration(description="x" * 256)), FailureType.ERROR)

    assert len(errors) == 1
    assert "at most 255 characters" in errors[0]


def test_validate_labeled_runner_requires_label():
    errors = failures_of_type(
        validate(default_configuration(code_scanning_default_setup_runner_type="labeled")), FailureType.ERROR
    )

    assert len(errors) == 1
    assert "no 'code_scanning_default_setup_runner_label'" in errors[0]


def test_validate_runner_label_without_labeled_runner():
    failures = validate(
        default_configuration(
            code_scanning_default_setup_runner_type="standard", code_scanning_default_setup_runner_label="label"
        )
    )

    assert failures_of_type(failures, FailureType.ERROR) == []
    assert len(failures_of_type(failures, FailureType.WARNING)) == 1


@pytest.mark.parametrize(
    ("reviewer", "message"),
    [
        ("@user", "invalid bypass reviewer"),
        ("security-team", "invalid bypass reviewer"),
        ("@org/team:sometimes", "with mode 'sometimes'"),
        ("#Triage", "with unknown role 'Triage'"),
    ],
)
def test_validate_invalid_bypass_reviewers(reviewer, message):
    configuration = default_configuration(
        secret_protection="enabled",
        secret_scanning="enabled",
        secret_scanning_push_protection="enabled",
        secret_scanning_delegated_bypass="enabled",
        secret_scanning_delegated_bypass_reviewers=[reviewer],
    )

    errors = failures_of_type(validate(configuration), FailureType.ERROR)

    assert len(errors) == 1
    assert message in errors[0]


@pytest.mark.parametrize(
    "reviewer",
    ["@org/team", "@org/team:exempt", "#OrganizationAdmin", "#Maintain:always", "#4711"],
)
def test_validate_valid_bypass_reviewers(reviewer):
    configuration = default_configuration(
        secret_protection="enabled",
        secret_scanning="enabled",
        secret_scanning_push_protection="enabled",
        secret_scanning_delegated_bypass="enabled",
        secret_scanning_delegated_bypass_reviewers=[reviewer],
    )

    assert validate(configuration) == []


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {
                "secret_protection": "enabled",
                "secret_scanning": "enabled",
                "secret_scanning_push_protection": "enabled",
                "secret_scanning_delegated_bypass": "enabled",
                "secret_scanning_delegated_bypass_reviewers": [],
            },
            "no 'secret_scanning_delegated_bypass_reviewers'",
        ),
        (
            {
                "secret_protection": "enabled",
                "secret_scanning": "disabled",
                "secret_scanning_validity_checks": "enabled",
            },
            "'secret_scanning_validity_checks' enabled while 'secret_scanning' is disabled",
        ),
        (
            {
                "secret_protection": "enabled",
                "secret_scanning": "enabled",
                "secret_scanning_delegated_bypass": "enabled",
            },
            "'secret_scanning_delegated_bypass' enabled while 'secret_scanning_push_protection' is disabled",
        ),
        (
            {"dependabot_alerts": "disabled", "dependabot_security_updates": "enabled"},
            "'dependabot_security_updates' enabled while 'dependabot_alerts' is disabled",
        ),
    ],
)
def test_validate_ineffective_settings(overrides, message):
    failures = validate(default_configuration(**overrides))

    assert failures_of_type(failures, FailureType.ERROR) == []
    warnings = failures_of_type(failures, FailureType.WARNING)
    assert len(warnings) == 1
    assert message in warnings[0]


@pytest.mark.parametrize(
    ("overrides", "messages"),
    [
        (
            {"code_scanning_default_setup": "enabled"},
            ["'code_scanning_default_setup' enabled while 'code_security' is disabled"],
        ),
        (
            {"secret_scanning": "enabled", "secret_scanning_push_protection": "enabled"},
            [
                "'secret_scanning' enabled while 'secret_protection' is disabled",
                "'secret_scanning_push_protection' enabled while 'secret_protection' is disabled",
            ],
        ),
    ],
)
def test_validate_features_require_their_product(overrides, messages):
    failures = validate(default_configuration(**overrides))

    errors = failures_of_type(failures, FailureType.ERROR)
    assert len(errors) == len(messages)
    for error, message in zip(errors, messages, strict=True):
        assert message in error


@pytest.mark.parametrize(
    "overrides",
    [
        {"code_security": "enabled", "code_scanning_default_setup": "enabled"},
        {"secret_protection": "enabled", "secret_scanning": "enabled", "secret_scanning_push_protection": "enabled"},
        # features that do not belong to a product
        {"dependabot_alerts": "enabled", "private_vulnerability_reporting": "enabled"},
    ],
)
def test_validate_features_with_their_product(overrides):
    assert validate(default_configuration(**overrides)) == []


@pytest.mark.parametrize(
    ("plan", "code_security", "secret_protection", "valid"),
    [
        ("free", "enabled", "enabled", True),
        ("free", "disabled", "disabled", True),
        ("free", "disabled", "enabled", False),
        ("free", "enabled", "disabled", False),
        # an unbundled Advanced Security plan is available for other plans
        ("team", "disabled", "enabled", True),
        ("enterprise", "enabled", "disabled", True),
    ],
)
def test_validate_products_of_the_plan(plan, code_security, secret_protection, valid):
    configuration = default_configuration(code_security=code_security, secret_protection=secret_protection)
    org = organization()
    org.settings.plan = plan
    context = validation_context()

    configuration.validate(context, org)

    errors = failures_of_type(context.validation_failures, FailureType.ERROR)
    if valid:
        assert errors == []
    else:
        assert len(errors) == 1
        assert "not available for an organization with free plan" in errors[0]


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, False),
        ({"code_security": "enabled"}, True),
        ({"secret_protection": "enabled"}, True),
        ({"secret_scanning": "enabled", "dependabot_alerts": "enabled"}, False),
    ],
)
def test_is_cost_related(overrides, expected):
    assert default_configuration(**overrides).is_cost_related(CostPolicy()) is expected


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"code_security": Change("disabled", "enabled")}, True),
        ({"secret_protection": Change("disabled", "enabled")}, True),
        ({"code_security": Change("enabled", "disabled")}, False),
        ({"default_for_new_repos": Change("none", "all")}, False),
    ],
)
def test_changes_are_cost_related(changes, expected):
    assert default_configuration().changes_are_cost_related(changes) is expected


# ---------------------------------------------------------------------------
# defaults for new repositories of an organization
# ---------------------------------------------------------------------------


def validate_defaults(
    configurations: list[OrganizationCodeSecurityConfiguration], defaults_disabled: bool = False
) -> list[str]:
    context = validation_context()
    organization = stub(
        code_security_configurations=configurations,
        settings=stub(default_code_security_configurations_disabled=defaults_disabled),
    )
    GitHubOrganization._validate_default_code_security_configurations(organization, context)  # type: ignore
    return failures_of_type(context.validation_failures, FailureType.ERROR)


def test_validate_defaults_for_distinct_visibilities():
    configurations = [
        default_configuration(name="public", default_for_new_repos="public"),
        default_configuration(name="private", default_for_new_repos="private_and_internal"),
        default_configuration(name="other"),
    ]

    assert validate_defaults(configurations) == []


@pytest.mark.parametrize(
    ("first", "second", "visibility"),
    [
        ("all", "public", "public"),
        ("private_and_internal", "all", "private_and_internal"),
        ("public", "public", "public"),
    ],
)
def test_validate_defaults_for_the_same_visibility(first, second, visibility):
    configurations = [
        default_configuration(name="first", default_for_new_repos=first),
        default_configuration(name="second", default_for_new_repos=second),
    ]

    errors = validate_defaults(configurations)

    assert len(errors) == 1
    assert f"default for new '{visibility}' repositories" in errors[0]
    assert "'first' is already the default" in errors[0]


def test_validate_defaults_while_default_configurations_are_disabled():
    configurations = [default_configuration(name="baseline", default_for_new_repos="all")]

    errors = validate_defaults(configurations, defaults_disabled=True)

    assert len(errors) == 1
    assert "'default_code_security_configurations_disabled'" in errors[0]

    # without a default configuration, the setting can be enabled
    assert validate_defaults([default_configuration(name="baseline")], defaults_disabled=True) == []


# ---------------------------------------------------------------------------
# code security configuration attached to a repository
# ---------------------------------------------------------------------------


def repository(**overrides: Any) -> Repository:
    data = jsonnet_evaluate_snippet(f"(import '{_EXAMPLE_CONFIG}').newRepo('my-repo')")
    data.update(overrides)
    return Repository.from_model_data(data)


def test_repository_without_code_security_configuration_keeps_the_attached_one():
    expected = repository()
    current = repository(code_security_configuration="baseline")

    assert expected.code_security_configuration is None
    assert "code_security_configuration" not in expected.get_difference_from(current)

    expected = repository(code_security_configuration="baseline")
    current = repository(code_security_configuration=None)

    assert expected.get_difference_from(current)["code_security_configuration"] == Change(None, "baseline")


async def test_repository_code_security_configuration_is_not_sent_with_the_repository_settings():
    repo = repository(code_security_configuration="baseline")

    provider_data = await repo.to_provider_data("OtterdogTest", MagicMock())

    assert "code_security_configuration" not in provider_data


def validate_repository(repo: Repository) -> list[str]:
    organization = GitHubOrganization.from_model_data(
        jsonnet_evaluate_snippet(f"(import '{_EXAMPLE_CONFIG}').newOrg('my-project', 'OtterdogTest')")
    )
    organization.add_code_security_configuration(default_configuration(name="baseline"))
    context = dataclasses.replace(validation_context(), root_object=organization)
    repo.validate(context, organization)
    return [m for m in failures_of_type(context.validation_failures, FailureType.ERROR) if "code_security" in m]


def test_repository_validate_code_security_configuration():
    assert validate_repository(repository(code_security_configuration="baseline")) == []

    errors = validate_repository(repository(code_security_configuration="unknown"))

    assert len(errors) == 1
    assert "no such code security configuration is defined" in errors[0]


@pytest.mark.parametrize(
    ("private", "to_value", "expected"),
    [
        (True, "baseline", True),
        (False, "baseline", False),
        (True, None, False),
    ],
)
def test_repository_attaching_code_security_configuration_is_cost_related(private, to_value, expected):
    repo = repository(private=private, code_security_configuration=to_value)

    changes = {"code_security_configuration": Change(None, to_value)}

    assert repo.changes_are_cost_related(changes) is expected


# ---------------------------------------------------------------------------
# loading from the provider
# ---------------------------------------------------------------------------


def organization() -> GitHubOrganization:
    return GitHubOrganization.from_model_data(
        jsonnet_evaluate_snippet(f"(import '{_EXAMPLE_CONFIG}').newOrg('my-project', 'OtterdogTest')")
    )


def configuration_with_id(
    name: str, configuration_id: int, target_type: str = "organization", **overrides: Any
) -> OrganizationCodeSecurityConfiguration:
    return dataclasses.replace(
        default_configuration(name=name, **overrides), id=configuration_id, target_type=target_type
    )


def test_add_code_security_configurations():
    org = organization()

    _add_code_security_configurations(
        org,
        "OtterdogTest",
        [
            {"id": 1, "name": "GitHub recommended", "target_type": "global", "advanced_security": "enabled"},
            {"id": 2, "name": "baseline", "target_type": "organization", "advanced_security": "disabled"},
            {"id": 3, "name": "enterprise", "target_type": "enterprise", "advanced_security": "enabled"},
        ],
    )

    # only configurations of the organization are managed, all of them are retained for planning
    assert [x.name for x in org.code_security_configurations] == ["baseline"]
    assert [x.name for x in unwrap(org.live_code_security_configurations)] == [
        "GitHub recommended",
        "baseline",
        "enterprise",
    ]


async def test_load_code_security_configuration_attachments():
    org = organization()
    live_configurations = [
        configuration_with_id("baseline", 1),
        configuration_with_id("strict", 2),
        configuration_with_id("GitHub recommended", 3, "global"),
        # an enterprise configuration with the same name as a configuration of the organization
        configuration_with_id("baseline", 4, "enterprise"),
    ]
    org.set_code_security_configurations(live_configurations[:2])
    org.set_live_code_security_configurations(live_configurations)
    for name in ("repo-a", "repo-b", "repo-c", "repo-d", "repo-e"):
        org.add_repository(repository(name=name, code_security_configuration=UNSET))

    attached = {1: ["repo-a"], 2: ["repo-b", "not-loaded"], 3: ["repo-c"], 4: ["repo-d"]}
    provider = stub(get_org_code_security_configuration_repositories=AsyncMock(side_effect=lambda _, x: attached[x]))

    await _load_code_security_configuration_attachments(org, "OtterdogTest", provider)  # type: ignore

    # repositories only reference managed configurations, identified by their id
    assert [r.code_security_configuration for r in org.repositories] == ["baseline", "strict", None, None, None]
    # while the attached configurations include configurations that are not managed
    assert org.attached_code_security_configurations == {
        "repo-a": 1,
        "repo-b": 2,
        "not-loaded": 2,
        "repo-c": 3,
        "repo-d": 4,
    }


async def test_load_code_security_configuration_attachments_fails_for_unmanaged_configurations():
    """Without the attachments of a configuration, repositories could be planned with conflicting settings."""
    org = organization()
    org.set_live_code_security_configurations([configuration_with_id("GitHub recommended", 1, "global")])
    provider = stub(get_org_code_security_configuration_repositories=AsyncMock(side_effect=RuntimeError("failed")))

    with pytest.raises(RuntimeError, match="failed"):
        await _load_code_security_configuration_attachments(org, "OtterdogTest", provider)  # type: ignore


async def test_load_code_security_configuration_metadata():
    """An organization loaded from a file retrieves what is needed to plan its repositories from GitHub."""
    org = organization()
    org.add_code_security_configuration(default_configuration(name="baseline"))
    org.add_repository(repository(name="repo-a", code_security_configuration="baseline"))
    org.add_repository(repository(name="repo-b", code_security_configuration=None))

    configurations = [
        {"id": 1, "name": "baseline", "target_type": "organization"},
        {"id": 2, "name": "not-in-file", "target_type": "organization"},
        {"id": 3, "name": "GitHub recommended", "target_type": "global"},
    ]
    attached = {1: ["repo-a"], 2: [], 3: ["repo-b"]}
    provider = stub(
        get_org_code_security_configurations=AsyncMock(return_value=configurations),
        get_org_code_security_configuration_repositories=AsyncMock(side_effect=lambda _, x: attached[x]),
    )

    await org.load_code_security_configuration_metadata(provider)  # type: ignore

    assert [x.name for x in unwrap(org.live_code_security_configurations)] == [
        "baseline",
        "not-in-file",
        "GitHub recommended",
    ]
    assert org.attached_code_security_configurations == {"repo-a": 1, "repo-b": 3}
    # the configurations and repositories of the file are left unchanged
    assert org.code_security_configurations[0].id is UNSET
    assert [r.code_security_configuration for r in org.repositories] == ["baseline", None]


async def test_enrich_team_bypass_reviewers():
    configurations = [
        {"secret_scanning_delegated_bypass_options": {"reviewers": [{"reviewer_id": 7, "reviewer_type": "TEAM"}]}},
        {"secret_scanning_delegated_bypass_options": {"reviewers": [{"reviewer_id": 5, "reviewer_type": "ROLE"}]}},
        {"secret_scanning_delegated_bypass_options": None},
    ]
    provider = stub(get_org_teams=AsyncMock(return_value=[{"id": 7, "slug": "security"}]))

    await _enrich_team_bypass_reviewers(configurations, "OtterdogTest", provider)  # type: ignore

    assert configurations[0]["secret_scanning_delegated_bypass_options"]["reviewers"][0]["team_slug"] == (
        "OtterdogTest/security"
    )
    assert "team_slug" not in configurations[1]["secret_scanning_delegated_bypass_options"]["reviewers"][0]


async def test_enrich_team_bypass_reviewers_without_teams_does_not_retrieve_teams():
    provider = stub(get_org_teams=AsyncMock())

    await _enrich_team_bypass_reviewers([{"name": "config"}], "OtterdogTest", provider)  # type: ignore

    provider.get_org_teams.assert_not_called()


@pytest.mark.parametrize("code_security_configuration", ["baseline", None])
async def test_repository_code_security_configuration_is_attached_on_creation(code_security_configuration):
    """The configuration is attached by add_repo, before the settings of the new repository are applied."""
    repo = repository(code_security_configuration=code_security_configuration)
    provider = AsyncMock()

    await LivePatch.of_addition(repo, None, Repository.apply_live_patch).apply("OtterdogTest", provider)

    provider.add_repo.assert_awaited_once()
    assert "code_security_configuration" not in provider.add_repo.await_args.args[1]
    assert provider.add_repo.await_args.kwargs["code_security_configuration"] == code_security_configuration
    provider.attach_org_code_security_configuration.assert_not_awaited()


async def test_repository_code_security_configuration_is_attached_before_the_settings_are_applied():
    current = repository(name="old-name", code_security_configuration="strict", dependabot_alerts_enabled=False)
    expected = repository(name="new-name", aliases=["old-name"], code_security_configuration="baseline")
    changes = {
        "name": Change("old-name", "new-name"),
        "code_security_configuration": Change("strict", "baseline"),
        "dependabot_alerts_enabled": Change(False, True),
    }
    provider = repository_provider()

    await LivePatch.of_changes(expected, current, changes, None, False, Repository.apply_live_patch).apply(
        "OtterdogTest", provider
    )

    calls = [
        call[0] for call in provider.mock_calls if call[0] in ("attach_org_code_security_configuration", "update_repo")
    ]
    assert calls == ["attach_org_code_security_configuration", "update_repo"]
    # the repository is renamed afterwards, it is attached with its current name
    provider.attach_org_code_security_configuration.assert_awaited_once_with("OtterdogTest", "baseline", ["old-name"])


# ---------------------------------------------------------------------------
# normalization of bypass reviewers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("reviewer", "normalized"),
    [
        ("#Maintain:always", "#Maintain"),
        ("#5", "#RepositoryAdmin"),
        ("#1:exempt", "#OrganizationAdmin:exempt"),
        ("#4711:always", "#4711"),
        ("@org/team:always", "@org/team"),
        ("@org/team:exempt", "@org/team:exempt"),
        # invalid reviewers are kept as is, to be reported by the validation
        ("#Triage:always", "#Triage:always"),
        ("@org/team:sometimes", "@org/team:sometimes"),
    ],
)
def test_bypass_reviewers_are_normalized(reviewer, normalized):
    configuration = default_configuration(secret_scanning_delegated_bypass_reviewers=[reviewer])

    assert configuration.secret_scanning_delegated_bypass_reviewers == [normalized]


def test_normalized_bypass_reviewers_do_not_differ_from_github():
    current = OrganizationCodeSecurityConfiguration.from_provider_data(
        "OtterdogTest",
        {
            "id": 1,
            "name": "baseline",
            "secret_scanning_delegated_bypass_options": {
                "reviewers": [
                    {"reviewer_id": 2, "reviewer_type": "ROLE", "mode": "ALWAYS"},
                    {"reviewer_id": 5, "reviewer_type": "ROLE", "mode": "ALWAYS"},
                ]
            },
        },
    )
    expected = default_configuration(secret_scanning_delegated_bypass_reviewers=["#Maintain:always", "#5"])

    assert "secret_scanning_delegated_bypass_reviewers" not in expected.get_difference_from(current)


# ---------------------------------------------------------------------------
# repository settings set by the attached code security configuration
# ---------------------------------------------------------------------------


def test_controlled_repository_properties():
    configuration = default_configuration(dependabot_security_updates="not_set", code_scanning_default_setup="not_set")

    assert configuration.get_controlled_repository_properties() == {
        "dependabot_alerts_enabled",
        "secret_scanning",
        "secret_scanning_push_protection",
        "private_vulnerability_reporting_enabled",
    }


def generate_repository_patches(
    expected: Repository, current: Repository | None, plan: CodeSecurityConfigurationPlan
) -> list[LivePatch]:
    org_settings = organization().settings
    context = LivePatchContext("OtterdogTest", "*", False, False, "*", org_settings, org_settings)
    context.code_security_configuration_plan = plan

    patches: list[LivePatch] = []
    Repository.generate_live_patch(expected, current, None, context, patches.append)
    return patches


def attached_plan(
    current: OrganizationCodeSecurityConfiguration,
    planned: OrganizationCodeSecurityConfiguration | None,
    managed: bool = True,
    update_released_settings: bool = False,
) -> CodeSecurityConfigurationPlan:
    """A plan where 'my-repo' is attached to a configuration that is planned to be changed or deleted."""
    return CodeSecurityConfigurationPlan(
        {current.name: planned} if managed and planned is not None else {},
        {"my-repo": current},
        {"my-repo": planned},
        {},
        update_released_settings,
    )


# the settings of the default repository differ from the default configuration
DIFFERING_SETTINGS = {
    "dependabot_alerts_enabled": False,
    "secret_scanning": "disabled",
}


def test_settings_set_by_the_configuration_specified_by_the_repository_are_not_managed():
    plan = CodeSecurityConfigurationPlan({"baseline": default_configuration(name="baseline")})
    expected = repository(code_security_configuration="baseline")
    current = repository(code_security_configuration=None, **DIFFERING_SETTINGS)

    patches = generate_repository_patches(expected, current, plan)

    assert len(patches) == 1
    assert unwrap(patches[0].changes) == {"code_security_configuration": Change(None, "baseline")}


@pytest.mark.parametrize("managed", [True, False])
def test_settings_set_by_the_attached_configuration_are_not_managed(managed):
    """This applies to configurations that are not managed as well, e.g. GitHub recommended."""
    attached = default_configuration(name="baseline" if managed else "GitHub recommended")
    plan = attached_plan(attached, attached, managed)
    expected = repository()
    current = repository(code_security_configuration="baseline" if managed else None, **DIFFERING_SETTINGS)

    assert expected.dependabot_alerts_enabled is True
    assert generate_repository_patches(expected, current, plan) == []


def test_settings_of_features_not_set_by_the_attached_configuration_are_managed():
    attached = default_configuration(name="baseline", dependabot_alerts="not_set")
    plan = attached_plan(attached, attached)
    expected = repository()
    current = repository(code_security_configuration="baseline", **DIFFERING_SETTINGS)

    patches = generate_repository_patches(expected, current, plan)

    assert len(patches) == 1
    assert unwrap(patches[0].changes) == {"dependabot_alerts_enabled": Change(False, True)}


@pytest.mark.parametrize("deleted", [True, False])
def test_settings_without_attached_configuration_are_managed(deleted):
    plan = (
        attached_plan(default_configuration(name="baseline"), None)
        if deleted
        else CodeSecurityConfigurationPlan({"baseline": default_configuration(name="baseline")})
    )
    expected = repository()
    current = repository(code_security_configuration=None, **DIFFERING_SETTINGS)

    patches = generate_repository_patches(expected, current, plan)

    assert len(patches) == 1
    assert set(unwrap(patches[0].changes)) == set(DIFFERING_SETTINGS)


@pytest.mark.parametrize(("private", "managed"), [(False, False), (True, True)])
def test_settings_of_new_repository_set_by_the_default_configuration_are_not_managed(private, managed):
    plan = CodeSecurityConfigurationPlan(default_configurations={"public": default_configuration(name="baseline")})
    expected = repository(private=private)

    patches = generate_repository_patches(expected, None, plan)

    assert len(patches) == 1
    assert (unwrap(patches[0].expected_object).dependabot_alerts_enabled is not UNSET) is managed
    # the expected organization is left unchanged
    assert expected.dependabot_alerts_enabled is True


@pytest.mark.parametrize("update_released_settings", [True, False])
def test_settings_released_by_the_attached_configuration(update_released_settings):
    """
    If the current values are not known, e.g. loaded from a file, the settings that the configuration stops setting
    are updated, as the configuration might have set them to other values on GitHub.
    """
    current_configuration = default_configuration(name="baseline")
    planned_configuration = default_configuration(name="baseline", dependabot_alerts="not_set")
    plan = attached_plan(
        current_configuration, planned_configuration, update_released_settings=update_released_settings
    )
    # the file holds the same value for the expected and current repository
    expected = repository()
    current = repository(code_security_configuration="baseline")

    patches = generate_repository_patches(expected, current, plan)

    if update_released_settings:
        assert len(patches) == 1
        assert unwrap(patches[0].changes) == {"dependabot_alerts_enabled": Change(True, True)}
    else:
        assert patches == []


# ---------------------------------------------------------------------------
# code security configurations planned for repositories
# ---------------------------------------------------------------------------


def current_organization(
    *configurations: OrganizationCodeSecurityConfiguration, attached: dict[str, int] | None = None
) -> GitHubOrganization:
    """An organization loaded from GitHub with the given configurations."""
    org = organization()
    org._loaded_from_github = True
    org.set_code_security_configurations([x for x in configurations if x.is_organization_configuration()])
    org.set_live_code_security_configurations(list(configurations))
    if attached is not None:
        org.set_attached_code_security_configurations(attached)
    return org


def plan(
    expected: GitHubOrganization, current: GitHubOrganization, delete_resources: bool = False
) -> CodeSecurityConfigurationPlan:
    return expected.plan_code_security_configurations(current, delete_resources)


def test_plan_keeps_values_not_managed_by_the_expected_configuration():
    current = current_organization(
        configuration_with_id("baseline", 1, dependabot_alerts="enabled", secret_scanning_generic_secrets="enabled"),
        attached={"my-repo": 1},
    )
    expected = organization()
    data = jsonnet_evaluate_snippet(f"(import '{_EXAMPLE_CONFIG}').newOrgCodeSecurityConfiguration('baseline')")
    data.pop("dependabot_alerts")
    expected.add_code_security_configuration(
        OrganizationCodeSecurityConfiguration.from_model_data({**data, "secret_scanning": "enabled"})
    )

    planned = plan(expected, current)

    assert planned.update_released_settings is False
    for planned_configuration in (
        planned.managed_configurations["baseline"],
        planned.planned_attached_configurations["my-repo"],
    ):
        assert planned_configuration is not None
        assert planned_configuration.id == 1
        # unset in the expected configuration
        assert planned_configuration.dependabot_alerts == "enabled"
        # optional property not managed by the expected configuration
        assert planned_configuration.secret_scanning_generic_secrets == "enabled"
        # managed by the expected configuration
        assert planned_configuration.secret_scanning == "enabled"
    # the current configuration is kept as is
    assert planned.current_attached_configurations["my-repo"].secret_scanning == "disabled"


@pytest.mark.parametrize("delete_resources", [False, True])
def test_plan_of_configurations_that_are_not_expected(delete_resources):
    current = current_organization(
        configuration_with_id("to-be-deleted", 1),
        configuration_with_id("GitHub recommended", 2, "global"),
        attached={"repo-a": 1, "repo-b": 2},
    )
    expected = organization()
    expected.add_code_security_configuration(default_configuration(name="new"))

    planned = plan(expected, current, delete_resources)

    if delete_resources:
        # the deleted configuration detaches its repositories
        assert set(planned.managed_configurations) == {"new"}
        assert planned.planned_attached_configurations["repo-a"] is None
    else:
        # the deletion of the configuration is skipped
        assert set(planned.managed_configurations) == {"to-be-deleted", "new"}
        assert unwrap(planned.planned_attached_configurations["repo-a"]).name == "to-be-deleted"

    # configurations that are not managed are kept, but can not be referenced by repositories
    assert unwrap(planned.planned_attached_configurations["repo-b"]).name == "GitHub recommended"


def test_plan_identifies_attached_configurations_by_their_id():
    current = current_organization(
        configuration_with_id("baseline", 1, dependabot_alerts="disabled"),
        configuration_with_id("baseline", 2, "enterprise", dependabot_alerts="enabled"),
        attached={"repo-a": 1, "repo-b": 2},
    )
    expected = organization()
    expected.add_code_security_configuration(default_configuration(name="baseline", dependabot_alerts="not_set"))

    planned = plan(expected, current)

    assert unwrap(planned.managed_configurations["baseline"]).id == 1
    assert unwrap(planned.managed_configurations["baseline"]).dependabot_alerts == "not_set"
    assert unwrap(planned.planned_attached_configurations["repo-a"]).dependabot_alerts == "not_set"
    # the enterprise configuration with the same name is not changed by the expected configuration
    assert unwrap(planned.planned_attached_configurations["repo-b"]).id == 2
    assert unwrap(planned.planned_attached_configurations["repo-b"]).dependabot_alerts == "enabled"


def test_plan_of_an_organization_loaded_from_a_file_with_live_metadata():
    """For a local apply, configurations of GitHub that are not in the file are retained to plan repositories."""
    current = organization()
    current.add_code_security_configuration(default_configuration(name="baseline"))
    current.set_live_code_security_configurations(
        [configuration_with_id("baseline", 1), configuration_with_id("not-in-file", 2)]
    )
    current.set_attached_code_security_configurations({"repo-a": 2})
    expected = organization()
    expected.add_code_security_configuration(default_configuration(name="baseline"))

    planned = plan(expected, current, delete_resources=True)

    # only configurations of the file are deleted
    assert unwrap(planned.planned_attached_configurations["repo-a"]).name == "not-in-file"
    assert planned.update_released_settings is True


def test_plan_of_an_organization_loaded_from_a_file_without_live_metadata():
    """For a local plan, the attachments are derived from the configurations referenced by repositories."""
    current = organization()
    current.add_code_security_configuration(default_configuration(name="baseline"))
    current.add_repository(repository(name="repo-a", code_security_configuration="baseline"))
    current.add_repository(repository(name="repo-b", code_security_configuration=None))
    expected = organization()
    expected.add_code_security_configuration(default_configuration(name="baseline", dependabot_alerts="not_set"))

    planned = plan(expected, current)

    assert set(planned.planned_attached_configurations) == {"repo-a"}
    assert unwrap(planned.planned_attached_configurations["repo-a"]).dependabot_alerts == "not_set"
    assert planned.current_attached_configurations["repo-a"].dependabot_alerts == "disabled"


def test_plan_of_defaults_prefers_the_expected_configurations():
    current = current_organization(
        configuration_with_id("old", 1, default_for_new_repos="all"),
        configuration_with_id("GitHub recommended", 2, "global", default_for_new_repos="public"),
    )
    expected = organization()
    expected.settings.default_code_security_configurations_disabled = False
    expected.add_code_security_configuration(default_configuration(name="old"))
    expected.add_code_security_configuration(
        default_configuration(name="new", default_for_new_repos="private_and_internal")
    )

    planned = plan(expected, current)

    # the expected configuration replaces the default for private repositories, the unmanaged one is still the
    # default for public repositories as 'old' is not the default anymore
    assert unwrap(planned.get_default_configuration(private=True)).name == "new"
    assert unwrap(planned.get_default_configuration(private=False)).name == "GitHub recommended"


def test_plan_of_defaults_while_default_configurations_are_disabled():
    current = current_organization(
        configuration_with_id("GitHub recommended", 1, "global", default_for_new_repos="all")
    )
    expected = organization()
    expected.settings.default_code_security_configurations_disabled = True

    planned = plan(expected, current)

    # the default configurations are removed before repositories are created
    assert planned.default_configurations == {}


def test_runner_label_of_standard_runners_is_not_compared():
    expected = default_configuration(
        code_scanning_default_setup_runner_type="standard", code_scanning_default_setup_runner_label="ignored"
    )
    current = default_configuration(
        code_scanning_default_setup_runner_type="standard", code_scanning_default_setup_runner_label=None
    )

    assert expected.get_difference_from(current) == {}


# ---------------------------------------------------------------------------
# fifth review: names, applied changes, archived repositories
# ---------------------------------------------------------------------------


def repository_provider(skipped_reason: str | None = None) -> AsyncMock:
    """A provider for the patches of repositories, whose patches are not skipped by default."""
    provider = AsyncMock()
    provider.get_skipped_repository_reason = MagicMock(return_value=skipped_reason)
    return provider


async def test_patch_of_repository_is_skipped_if_its_configuration_is_not_applied():
    current = repository(dependabot_alerts_enabled=False)
    expected = repository()
    provider = repository_provider("the update of code security configuration 'baseline' is not applied")

    patch = LivePatch.of_changes(
        expected,
        current,
        {"dependabot_alerts_enabled": Change(False, True)},
        None,
        False,
        Repository.apply_live_patch,
    )

    with pytest.raises(RuntimeError, match="skipped the patch of the repository, the update of"):
        await patch.apply("OtterdogTest", provider)

    provider.get_skipped_repository_reason.assert_called_once_with("OtterdogTest", "my-repo")
    provider.update_repo.assert_not_awaited()


def test_attached_configurations_are_looked_up_regardless_of_the_case_of_the_repository():
    attached = default_configuration(name="baseline")
    plan = attached_plan(attached, attached)
    expected = repository(name="My-Repo")
    current = repository(name="My-Repo", code_security_configuration="baseline", **DIFFERING_SETTINGS)

    assert generate_repository_patches(expected, current, plan) == []


async def test_attachments_are_keyed_by_the_lower_case_name_of_repositories():
    org = organization()
    org.set_code_security_configurations([configuration_with_id("baseline", 1)])
    org.set_live_code_security_configurations(org.code_security_configurations)
    org.add_repository(repository(name="My-Repo", code_security_configuration=UNSET))
    provider = stub(get_org_code_security_configuration_repositories=AsyncMock(return_value=["My-Repo"]))

    await _load_code_security_configuration_attachments(org, "OtterdogTest", provider)  # type: ignore

    assert org.attached_code_security_configurations == {"my-repo": 1}
    assert org.repositories[0].code_security_configuration == "baseline"


def file_organization(*configurations: OrganizationCodeSecurityConfiguration) -> GitHubOrganization:
    """A current organization loaded from a file, whose configurations differ from the ones on GitHub."""
    org = organization()
    org.set_code_security_configurations(list(configurations))
    org.set_live_code_security_configurations([configuration_with_id("baseline", 1, secret_scanning="disabled")])
    org.set_attached_code_security_configurations({"my-repo": 1})
    return org


def test_plan_keeps_the_configuration_on_github_if_it_is_not_updated():
    """If the file and the expected configuration do not differ, no patch updates the configuration on GitHub."""
    configuration = default_configuration(name="baseline", secret_scanning="not_set")
    expected = organization()
    expected.add_code_security_configuration(configuration)

    planned = plan(expected, file_organization(configuration))

    assert unwrap(planned.get_planned_attached_configuration("my-repo")).secret_scanning == "disabled"


def test_plan_applies_all_expected_settings_if_the_configuration_is_updated():
    expected = organization()
    expected.add_code_security_configuration(
        default_configuration(name="baseline", secret_scanning="not_set", dependabot_alerts="enabled")
    )

    planned = plan(expected, file_organization(default_configuration(name="baseline", secret_scanning="not_set")))

    planned_configuration = unwrap(planned.get_planned_attached_configuration("my-repo"))
    assert planned_configuration.dependabot_alerts == "enabled"
    # the update sends all settings of the expected configuration
    assert planned_configuration.secret_scanning == "not_set"


def test_plan_only_applies_the_default_if_only_the_default_is_updated():
    expected = organization()
    expected.settings.default_code_security_configurations_disabled = False
    expected.add_code_security_configuration(
        default_configuration(name="baseline", secret_scanning="not_set", default_for_new_repos="all")
    )

    planned = plan(expected, file_organization(default_configuration(name="baseline", secret_scanning="not_set")))

    planned_configuration = unwrap(planned.get_planned_attached_configuration("my-repo"))
    assert planned_configuration.default_for_new_repos == "all"
    assert planned_configuration.secret_scanning == "disabled"


def test_plan_of_an_enterprise_configuration_named_like_a_deleted_one():
    current = current_organization(
        configuration_with_id("baseline", 1),
        configuration_with_id("baseline", 2, "enterprise"),
        attached={"repo-a": 2},
    )

    planned = plan(organization(), current, delete_resources=True)

    assert unwrap(planned.get_planned_attached_configuration("repo-a")).id == 2


def test_code_security_configuration_of_archived_repositories_is_managed():
    """GitHub supports code security configurations on archived repositories."""
    expected = repository(archived=True, code_security_configuration="baseline")
    current = repository(archived=True, code_security_configuration=None)

    assert expected.get_difference_from(current)["code_security_configuration"] == Change(None, "baseline")


async def test_repository_is_unarchived_before_attaching_a_configuration():
    current = repository(archived=True, code_security_configuration=None)
    expected = repository(archived=False, code_security_configuration="baseline")
    changes = {
        "archived": Change(True, False),
        "code_security_configuration": Change(None, "baseline"),
        "dependabot_alerts_enabled": Change(False, True),
    }
    provider = repository_provider()

    await LivePatch.of_changes(expected, current, changes, None, False, Repository.apply_live_patch).apply(
        "OtterdogTest", provider
    )

    calls = [
        (call[0], call[1][2] if call[0] == "update_repo" else None)
        for call in provider.mock_calls
        if call[0] in ("attach_org_code_security_configuration", "update_repo")
    ]
    assert calls == [
        ("update_repo", {"archived": False}),
        ("attach_org_code_security_configuration", None),
        ("update_repo", {"dependabot_alerts_enabled": True}),
    ]


# ---------------------------------------------------------------------------
# effective settings of repositories, e.g. for the dashboard
# ---------------------------------------------------------------------------


def test_repository_settings_of_a_configuration():
    configuration = default_configuration(
        dependabot_alerts="enabled",
        secret_scanning="enabled",
        code_scanning_default_setup="not_set",
        private_vulnerability_reporting="not_set",
    )

    assert configuration.get_repository_settings() == {
        "dependabot_alerts_enabled": True,
        "dependabot_security_updates_enabled": False,
        "secret_scanning": "enabled",
        "secret_scanning_push_protection": "disabled",
    }


def test_repository_settings_of_a_configuration_for_a_private_repository():
    configuration = default_configuration(private_vulnerability_reporting="enabled")

    assert configuration.get_repository_settings()["private_vulnerability_reporting_enabled"] is True
    # GitHub supports private vulnerability reporting only on public repositories
    assert "private_vulnerability_reporting_enabled" not in configuration.get_repository_settings(private=True)


def test_effective_repository():
    org = organization()
    org.add_code_security_configuration(default_configuration(name="baseline", dependabot_alerts="disabled"))
    attached = repository(name="attached", dependabot_alerts_enabled=True, code_security_configuration="baseline")
    unattached = repository(name="unattached", dependabot_alerts_enabled=True, code_security_configuration=None)
    unknown = repository(name="unknown", dependabot_alerts_enabled=True, code_security_configuration="unknown")

    assert org.get_effective_repository(attached).dependabot_alerts_enabled is False
    # the repository itself is left unchanged
    assert attached.dependabot_alerts_enabled is True
    # repositories that do not reference a defined configuration keep their own settings
    assert org.get_effective_repository(unattached) is unattached
    assert org.get_effective_repository(unknown) is unknown


def test_effective_private_repository():
    org = organization()
    org.add_code_security_configuration(
        default_configuration(name="baseline", dependabot_alerts="disabled", private_vulnerability_reporting="enabled")
    )
    private = repository(
        private=True,
        dependabot_alerts_enabled=True,
        private_vulnerability_reporting_enabled=False,
        code_security_configuration="baseline",
    )

    effective = org.get_effective_repository(private)

    assert effective.dependabot_alerts_enabled is False
    # the configuration does not enable private vulnerability reporting on a private repository
    assert effective.private_vulnerability_reporting_enabled is False
