#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from otterdog.config import OtterdogConfig
from otterdog.credentials.inmemory_provider import InMemoryVault
from otterdog.jsonnet import JsonnetConfig
from otterdog.models import FailureType, ValidationContext
from otterdog.models.environment_secret import EnvironmentSecret
from otterdog.models.github_organization import GitHubOrganization
from otterdog.models.organization_codespaces_secret import OrganizationCodespacesSecret
from otterdog.models.organization_dependabot_secret import OrganizationDependabotSecret
from otterdog.models.organization_secret import OrganizationSecret
from otterdog.models.organization_settings import OrganizationSettings
from otterdog.models.repo_codespaces_secret import RepositoryCodespacesSecret
from otterdog.models.repo_dependabot_secret import RepositoryDependabotSecret
from otterdog.models.repo_secret import RepositorySecret
from otterdog.models.repository import Repository
from otterdog.providers.github import GitHubProvider
from otterdog.utils import jsonnet_evaluate_snippet


def _organization_data() -> dict:
    return {
        "project_name": "project",
        "github_id": "test-org",
        "settings": {"name": "test-org"},
        "dependabot_secrets": [{"name": "DEPENDABOT_SECRET", "value": "********", "visibility": "private"}],
        "codespaces_secrets": [{"name": "CODESPACES_SECRET", "value": "********", "visibility": "private"}],
    }


def test_organization_configuration_builds_typed_special_secrets() -> None:
    organization = GitHubOrganization.from_model_data(_organization_data())

    assert isinstance(organization.dependabot_secrets[0], OrganizationDependabotSecret)
    assert isinstance(organization.codespaces_secrets[0], OrganizationCodespacesSecret)


def test_organization_secret_copy_does_not_cross_scope() -> None:
    expected = GitHubOrganization.from_model_data(_organization_data())
    source = GitHubOrganization.from_model_data(
        {
            **_organization_data(),
            "secrets": [{"name": "DEPENDABOT_SECRET", "value": "ordinary-value", "visibility": "private"}],
            "dependabot_secrets": [{"name": "DEPENDABOT_SECRET", "value": "dependabot-value", "visibility": "private"}],
        }
    )

    expected.copy_secrets(source)

    assert expected.dependabot_secrets[0].value == "dependabot-value"


def test_repository_configuration_builds_typed_special_secrets() -> None:
    settings = OrganizationSettings.from_model_data({"name": "test-org"})
    repository = Repository.from_model_data(
        {
            "name": "test-repo",
            "dependabot_secrets": [{"name": "DEPENDABOT_SECRET", "value": "value"}],
            "codespaces_secrets": [{"name": "CODESPACES_SECRET", "value": "value"}],
        }
    ).coerce_from_org_settings(settings)

    assert isinstance(repository.dependabot_secrets[0], RepositoryDependabotSecret)
    assert isinstance(repository.codespaces_secrets[0], RepositoryCodespacesSecret)


def test_bundled_template_exports_special_secret_constructors() -> None:
    """The documented default template exposes every supported secret scope."""
    functions = (
        "newOrgDependabotSecret",
        "newOrgCodespacesSecret",
        "newRepoDependabotSecret",
        "newRepoCodespacesSecret",
    )

    for function in functions:
        result = jsonnet_evaluate_snippet(
            f"(import './examples/template/otterdog-defaults.libsonnet').{function}('default')"
        )
        assert result["name"] == "default"


@pytest.mark.parametrize(
    ("secret_class", "additional_data"),
    [
        (OrganizationSecret, {"visibility": "public", "selected_repositories": []}),
        (OrganizationDependabotSecret, {"visibility": "public", "selected_repositories": []}),
        (OrganizationCodespacesSecret, {"visibility": "public", "selected_repositories": []}),
        (RepositorySecret, {}),
        (RepositoryDependabotSecret, {}),
        (RepositoryCodespacesSecret, {}),
        (EnvironmentSecret, {}),
    ],
)
def test_secret_names_must_be_uppercase(secret_class: type, additional_data: dict) -> None:
    """Every secret scope rejects names that GitHub will normalize on import."""
    secret = secret_class(name="mixedCaseSecret", value="********", **additional_data)
    context = ValidationContext(
        root_object=None,
        secret_resolver=InMemoryVault(),
        template_dir="",
        org_members=set(),
        default_team_names=set(),
        exclude_teams_pattern=None,
    )

    secret.validate(context, None)

    assert any(
        failure_type == FailureType.ERROR and "not uppercase" in message
        for failure_type, message in context.validation_failures
    )


async def _validate_organization(organization: GitHubOrganization) -> ValidationContext:
    config = MagicMock(spec=OtterdogConfig, exclude_teams_pattern=None)
    jsonnet_config = MagicMock(spec=JsonnetConfig, template_dir="")
    jsonnet_config.default_org_config_for_org_id.return_value = {
        "project_name": "project",
        "github_id": "test-org",
        "settings": {"name": "test-org"},
    }
    return await organization.validate(config, jsonnet_config, InMemoryVault(), MagicMock(spec=GitHubProvider))


@pytest.mark.parametrize("scope", ["dependabot_secrets", "codespaces_secrets"])
@pytest.mark.parametrize(
    ("name", "expected_error"),
    [("mixedCaseSecret", "not uppercase"), ("GITHUB_TOKEN", "starts with prefix 'GITHUB_'")],
)
async def test_organization_validation_checks_repository_special_secret_names(
    scope: str, name: str, expected_error: str
) -> None:
    organization = GitHubOrganization.from_model_data(
        {
            "project_name": "project",
            "github_id": "test-org",
            "settings": {"name": "test-org"},
            "repositories": [{"name": "test-repo", "private": False, scope: [{"name": name, "value": "********"}]}],
        }
    )

    context = await _validate_organization(organization)

    assert any(
        failure_type == FailureType.ERROR and expected_error in message
        for failure_type, message in context.validation_failures
    )


@pytest.mark.parametrize("scope", ["secrets", "dependabot_secrets", "codespaces_secrets"])
@pytest.mark.parametrize("visibility", ["public", "private", "selected", "invalid"])
async def test_free_plan_organization_secret_visibility(scope: str, visibility: str) -> None:
    """Organization Actions and Codespaces private secrets require a paid plan."""
    organization = GitHubOrganization.from_model_data(
        {
            "project_name": "project",
            "github_id": "test-org",
            "settings": {"name": "test-org", "plan": "free"},
            scope: [{"name": "TEST_SECRET", "value": "********", "visibility": "public"}],
        }
    )
    secret = getattr(organization, scope)[0]
    secret.visibility = visibility
    secret.selected_repositories = ["test-repo"]

    context = await _validate_organization(organization)

    errors = [message for failure_type, message in context.validation_failures if failure_type == FailureType.ERROR]
    if visibility == "invalid":
        assert len(errors) == 1
        assert "only values ('public' | 'private' | 'selected') are allowed" in errors[0]
    elif scope in {"secrets", "codespaces_secrets"} and visibility == "private":
        assert len(errors) == 1
        assert "not available for an organization with free plan" in errors[0]
    else:
        assert errors == []

    ignored_repositories = [
        message
        for failure_type, message in context.validation_failures
        if failure_type == FailureType.WARNING and "'selected_repositories'" in message
    ]
    assert bool(ignored_repositories) == (visibility != "selected")
