#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import dataclasses
from typing import Any

import pytest

from otterdog.models import LivePatch
from otterdog.models.organization_code_security_configuration import OrganizationCodeSecurityConfiguration
from otterdog.models.repository import Repository
from otterdog.utils import Change, jsonnet_evaluate_snippet

from .conftest import GitHubProviderTestKit
from .helpers.model import ModelForContext

# Constants
ORG_ID = "test-org"
REPO_NAME = "test-repo"
CONFIGURATIONS_URL = f"/orgs/{ORG_ID}/code-security/configurations"

_DEFAULTS = "./otterdog/resources/defaults/otterdog-defaults.libsonnet"

# the request to create or update a configuration with the settings of the default configuration
DEFAULT_CONFIGURATION_REQUEST = {
    "name": "baseline",
    "description": "",
    "code_security": "disabled",
    "secret_protection": "disabled",
    "advanced_security": "disabled",
    "dependency_graph": "enabled",
    "dependency_graph_autosubmit_action": "disabled",
    "dependabot_alerts": "disabled",
    "dependabot_security_updates": "disabled",
    "code_scanning_default_setup": "disabled",
    "secret_scanning": "disabled",
    "secret_scanning_push_protection": "disabled",
    "secret_scanning_delegated_bypass": "disabled",
    "secret_scanning_validity_checks": "disabled",
    "secret_scanning_non_provider_patterns": "disabled",
    "private_vulnerability_reporting": "disabled",
    "enforcement": "enforced",
}


def configuration(configuration_id: int | None = None, **overrides: Any) -> OrganizationCodeSecurityConfiguration:
    data = jsonnet_evaluate_snippet(f"(import '{_DEFAULTS}').newOrgCodeSecurityConfiguration('baseline')")
    data.update(overrides)
    result = OrganizationCodeSecurityConfiguration.from_model_data(data)
    if configuration_id is not None:
        result = dataclasses.replace(result, id=configuration_id)
    return result


async def generate_patch_and_run_it(
    github: GitHubProviderTestKit,
    *,
    old: OrganizationCodeSecurityConfiguration | None,
    new: OrganizationCodeSecurityConfiguration | None,
):
    """Generate and apply a LivePatch in one call."""
    model = ModelForContext(ORG_ID)

    patch = model.generate_live_patch(old=old, new=new)
    await patch.apply(ORG_ID, github.provider)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Retrieval of code security configurations
# ---------------------------------------------------------------------------


async def test_get_configurations(github: GitHubProviderTestKit):
    """All configurations are returned with their default for new repositories, the ones of GitHub included."""
    # API: https://docs.github.com/en/rest/code-security/configurations#get-code-security-configurations-for-an-organization
    github.http.expect(
        "GET",
        CONFIGURATIONS_URL,
        request_params={"per_page": "100"},
        response_json=[
            {"id": 1, "name": "GitHub recommended", "target_type": "global"},
            {"id": 2, "name": "baseline", "target_type": "organization"},
        ],
        response_links={"next": {"url": f"https://api.github.com{CONFIGURATIONS_URL}?per_page=100&after=cursor"}},
    )
    github.http.expect(
        "GET",
        CONFIGURATIONS_URL,
        request_params={"per_page": "100", "after": "cursor"},
        response_json=[
            {"id": 3, "name": "enterprise", "target_type": "enterprise"},
            {"id": 4, "name": "strict", "target_type": "organization"},
        ],
    )
    # API: https://docs.github.com/en/rest/code-security/configurations#get-default-code-security-configurations
    github.http.expect(
        "GET",
        f"{CONFIGURATIONS_URL}/defaults",
        response_json=[
            {"default_for_new_repos": "public", "configuration": {"id": 1}},
            {"default_for_new_repos": "private_and_internal", "configuration": {"id": 4}},
        ],
    )

    configurations = await github.provider.get_org_code_security_configurations(ORG_ID)

    assert [(c["name"], c["target_type"], c["default_for_new_repos"]) for c in configurations] == [
        ("GitHub recommended", "global", "public"),
        ("baseline", "organization", "none"),
        ("enterprise", "enterprise", "none"),
        ("strict", "organization", "private_and_internal"),
    ]


async def test_resolve_configuration_id_of_the_organization_only(github: GitHubProviderTestKit):
    """A configuration is attached by its name, only configurations of the organization are considered."""
    github.http.expect(
        "GET",
        CONFIGURATIONS_URL,
        request_params={"per_page": "100"},
        response_json=[
            {"id": 1, "name": "baseline", "target_type": "enterprise"},
            {"id": 2, "name": "baseline", "target_type": "organization"},
        ],
    )

    assert await github.provider.rest_api.org.get_code_security_configuration_id(ORG_ID, "baseline") == 2


async def test_get_configuration_repositories(github: GitHubProviderTestKit):
    """Only repositories the configuration is attached to are returned."""
    # API: https://docs.github.com/en/rest/code-security/configurations#get-repositories-associated-with-a-code-security-configuration
    github.http.expect(
        "GET",
        f"{CONFIGURATIONS_URL}/2/repositories",
        request_params={"per_page": "100", "status": "attached,attaching,updating,enforced"},
        response_json=[
            {"status": "attached", "repository": {"id": 10, "name": "repo-a"}},
            {"status": "enforced", "repository": {"id": 11, "name": "repo-b"}},
        ],
    )

    assert await github.provider.get_org_code_security_configuration_repositories(ORG_ID, 2) == ["repo-a", "repo-b"]


# ---------------------------------------------------------------------------
# CRUD operations for OrganizationCodeSecurityConfiguration
# ---------------------------------------------------------------------------


async def test_create(github: GitHubProviderTestKit):
    # API: https://docs.github.com/en/rest/code-security/configurations#create-a-code-security-configuration
    github.http.expect(
        "POST",
        CONFIGURATIONS_URL,
        request_json=DEFAULT_CONFIGURATION_REQUEST,
        response_status=201,
        response_json={"id": 7, "name": "baseline"},
    )

    await generate_patch_and_run_it(github, old=None, new=configuration())


async def test_create_as_default_for_new_repositories(github: GitHubProviderTestKit):
    github.http.expect(
        "POST",
        CONFIGURATIONS_URL,
        # 'advanced_security' would need a deprecated value, only the individual products are set
        request_json={
            **{k: v for k, v in DEFAULT_CONFIGURATION_REQUEST.items() if k != "advanced_security"},
            "code_security": "enabled",
            "secret_protection": "disabled",
            "secret_scanning": "enabled",
            "secret_scanning_push_protection": "enabled",
            "secret_scanning_delegated_bypass": "enabled",
            "secret_scanning_delegated_bypass_options": {
                "reviewers": [{"reviewer_id": 5, "reviewer_type": "ROLE", "mode": "ALWAYS"}]
            },
        },
        response_status=201,
        response_json={"id": 7, "name": "baseline"},
    )
    # API: https://docs.github.com/en/rest/code-security/configurations#set-a-code-security-configuration-as-a-default-for-an-organization
    github.http.expect(
        "PUT",
        f"{CONFIGURATIONS_URL}/7/defaults",
        request_json={"default_for_new_repos": "all"},
        response_json={"default_for_new_repos": "all", "configuration": {"id": 7}},
    )

    await generate_patch_and_run_it(
        github,
        old=None,
        new=configuration(
            code_security="enabled",
            secret_scanning="enabled",
            secret_scanning_push_protection="enabled",
            secret_scanning_delegated_bypass="enabled",
            secret_scanning_delegated_bypass_reviewers=["#RepositoryAdmin"],
            default_for_new_repos="all",
        ),
    )


async def test_update(github: GitHubProviderTestKit):
    # API: https://docs.github.com/en/rest/code-security/configurations#update-a-code-security-configuration
    github.http.expect(
        "PATCH",
        f"{CONFIGURATIONS_URL}/7",
        request_json={**DEFAULT_CONFIGURATION_REQUEST, "dependabot_alerts": "enabled"},
        response_json={"id": 7, "name": "baseline"},
    )

    await generate_patch_and_run_it(
        github,
        old=configuration(7),
        new=configuration(dependabot_alerts="enabled"),
    )


async def test_update_without_effective_change(github: GitHubProviderTestKit):
    """GitHub responds with 204 if the update does not change the configuration, which is not an error."""
    github.http.expect(
        "PATCH",
        f"{CONFIGURATIONS_URL}/7",
        request_json={**DEFAULT_CONFIGURATION_REQUEST, "description": "updated"},
        response_status=204,
    )

    await generate_patch_and_run_it(github, old=configuration(7), new=configuration(description="updated"))


async def test_update_failure(github: GitHubProviderTestKit):
    github.http.expect(
        "PATCH",
        f"{CONFIGURATIONS_URL}/7",
        request_json={**DEFAULT_CONFIGURATION_REQUEST, "description": "updated"},
        response_status=422,
        response_json={"message": "Validation Failed"},
    )

    patch = ModelForContext(ORG_ID).generate_live_patch(old=configuration(7), new=configuration(description="updated"))

    with pytest.raises(RuntimeError, match="failed to update code security configuration with name 'baseline'"):
        await patch.apply(ORG_ID, github.provider)  # type: ignore[arg-type]


async def test_update_default_for_new_repositories_only(github: GitHubProviderTestKit):
    """A change of the default for new repositories does not update the configuration itself."""
    github.http.expect(
        "PUT",
        f"{CONFIGURATIONS_URL}/7/defaults",
        request_json={"default_for_new_repos": "public"},
        response_json={"default_for_new_repos": "public", "configuration": {"id": 7}},
    )

    await generate_patch_and_run_it(
        github,
        old=configuration(7, default_for_new_repos="none"),
        new=configuration(default_for_new_repos="public"),
    )


async def test_delete(github: GitHubProviderTestKit):
    # API: https://docs.github.com/en/rest/code-security/configurations#delete-a-code-security-configuration
    github.http.expect("DELETE", f"{CONFIGURATIONS_URL}/7", response_status=204)

    await generate_patch_and_run_it(github, old=configuration(7), new=None)


async def test_delete_default_configuration(github: GitHubProviderTestKit):
    """A configuration that is the default for new repositories stops being the default before it is deleted."""
    github.http.expect(
        "PUT",
        f"{CONFIGURATIONS_URL}/7/defaults",
        request_json={"default_for_new_repos": "none"},
        response_json={"default_for_new_repos": "none", "configuration": {"id": 7}},
    )
    github.http.expect("DELETE", f"{CONFIGURATIONS_URL}/7", response_status=204)

    await generate_patch_and_run_it(github, old=configuration(7, default_for_new_repos="all"), new=None)


# ---------------------------------------------------------------------------
# Attaching a code security configuration to a repository
# ---------------------------------------------------------------------------


async def test_attach_to_repository(github: GitHubProviderTestKit):
    # the id of the configuration and of the repository are resolved by their name
    github.http.expect(
        "GET",
        CONFIGURATIONS_URL,
        request_params={"per_page": "100"},
        response_json=[{"id": 7, "name": "baseline", "target_type": "organization"}],
    )
    github.http.expect("GET", f"/repos/{ORG_ID}/{REPO_NAME}", response_json={"id": 1296269, "name": REPO_NAME})
    # API: https://docs.github.com/en/rest/code-security/configurations#attach-a-configuration-to-repositories
    github.http.expect(
        "POST",
        f"{CONFIGURATIONS_URL}/7/attach",
        request_json={"scope": "selected", "selected_repository_ids": [1296269]},
        response_status=202,
        response_json={},
    )

    current = Repository.from_model_data({"name": REPO_NAME, "code_security_configuration": None})
    expected = Repository.from_model_data({"name": REPO_NAME, "code_security_configuration": "baseline"})
    patch = LivePatch.of_changes(
        expected,
        current,
        {"code_security_configuration": Change(None, "baseline")},
        None,
        False,
        Repository.apply_live_patch,
    )

    await patch.apply(ORG_ID, github.provider)  # type: ignore[arg-type]
