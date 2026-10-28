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
from otterdog.models import CostPolicy, FailureType, LivePatch, ModelObject, ValidationContext
from otterdog.models.github_organization import (
    GitHubOrganization,
    _enrich_team_bypass_reviewers,
    _load_code_security_configuration_attachments,
)
from otterdog.models.organization_code_security_configuration import (
    OrganizationCodeSecurityConfiguration,
)
from otterdog.models.repository import Repository
from otterdog.utils import UNSET, Change, jsonnet_evaluate_snippet

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
        # a deprecated value of 'advanced_security' is not used, the individual products are set instead
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

        assert provider_data["advanced_security"] == "disabled"
        assert provider_data["code_security"] == "disabled"
        assert provider_data["secret_protection"] == "disabled"

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
    configuration = OrganizationCodeSecurityConfiguration.from_provider_data(
        "OtterdogTest", {"id": 1, "name": "config", "advanced_security": advanced_security}
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
async def test_advanced_security_is_only_sent_without_deprecated_value(
    code_security, secret_protection, advanced_security
):
    configuration = default_configuration(code_security=code_security, secret_protection=secret_protection)

    provider_data = await configuration.to_provider_data("OtterdogTest", MagicMock())

    assert provider_data.get("advanced_security") == advanced_security
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
                "secret_scanning": "enabled",
                "secret_scanning_push_protection": "enabled",
                "secret_scanning_delegated_bypass": "enabled",
                "secret_scanning_delegated_bypass_reviewers": [],
            },
            "no 'secret_scanning_delegated_bypass_reviewers'",
        ),
        (
            {"secret_scanning": "disabled", "secret_scanning_validity_checks": "enabled"},
            "'secret_scanning_validity_checks' enabled while 'secret_scanning' is disabled",
        ),
        (
            {"secret_scanning": "enabled", "secret_scanning_delegated_bypass": "enabled"},
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


async def test_load_code_security_configuration_attachments():
    org = GitHubOrganization.from_model_data(
        jsonnet_evaluate_snippet(f"(import '{_EXAMPLE_CONFIG}').newOrg('my-project', 'OtterdogTest')")
    )
    org.add_code_security_configuration(dataclasses.replace(default_configuration(name="baseline"), id=1))
    org.add_code_security_configuration(dataclasses.replace(default_configuration(name="strict"), id=2))
    for name in ("repo-a", "repo-b", "repo-c"):
        org.add_repository(repository(name=name, code_security_configuration=UNSET))

    attached = {1: ["repo-a"], 2: ["repo-b", "not-loaded"]}
    provider = stub(get_org_code_security_configuration_repositories=AsyncMock(side_effect=lambda _, x: attached[x]))

    await _load_code_security_configuration_attachments(org, "OtterdogTest", provider)  # type: ignore

    assert [r.code_security_configuration for r in org.repositories] == ["baseline", "strict", None]


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


@pytest.mark.parametrize(("code_security_configuration", "attached"), [("baseline", True), (None, False)])
async def test_repository_code_security_configuration_is_attached_after_creation(code_security_configuration, attached):
    repo = repository(code_security_configuration=code_security_configuration)
    provider = AsyncMock()

    await LivePatch.of_addition(repo, None, Repository.apply_live_patch).apply("OtterdogTest", provider)

    provider.add_repo.assert_awaited_once()
    assert "code_security_configuration" not in provider.add_repo.await_args.args[1]
    if attached:
        provider.attach_org_code_security_configuration.assert_awaited_once_with(
            "OtterdogTest", "baseline", ["my-repo"]
        )
    else:
        provider.attach_org_code_security_configuration.assert_not_awaited()
