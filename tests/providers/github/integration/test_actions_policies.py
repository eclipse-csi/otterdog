#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import dataclasses
from typing import Any

from otterdog.models.github_organization import _enrich_actions_policy_actors
from otterdog.models.organization_actions_policy import OrganizationActionsPolicy
from otterdog.models.repo_actions_policy import RepositoryActionsPolicy
from otterdog.utils import UNSET, jsonnet_evaluate_snippet

from .conftest import GitHubProviderTestKit
from .helpers.model import ModelForContext

# Constants
ORG_ID = "test-org"
REPO_NAME = "test-repo"
ORG_POLICIES_URL = f"/orgs/{ORG_ID}/actions/policies"
REPO_POLICIES_URL = f"/repos/{ORG_ID}/{REPO_NAME}/actions/policies"
LIST_PARAMS: dict[str, str | int | bool] = {"per_page": "100", "has_parents": "false"}

_DEFAULTS = "./otterdog/resources/defaults/otterdog-defaults.libsonnet"

EVENTS_RULE = {"type": "restrict_action_events", "parameters": {"allowed_events": ["push"]}}
# a rule whose type GitHub does not publish in its API yet
LOCKFILE_RULE = {"type": "require_lockfile"}


def org_policy(policy_id: Any = UNSET, **overrides: Any) -> OrganizationActionsPolicy:
    data = jsonnet_evaluate_snippet(f"(import '{_DEFAULTS}').newOrgActionsPolicy('pinned')")
    data.update({"include_repo_names": ["~ALL"], "allowed_events": ["push"], **overrides})
    return dataclasses.replace(OrganizationActionsPolicy.from_model_data(data), id=policy_id)


def repo_policy(policy_id: Any = UNSET, **overrides: Any) -> RepositoryActionsPolicy:
    data = jsonnet_evaluate_snippet(f"(import '{_DEFAULTS}').newRepoActionsPolicy('pinned')")
    data.update({"allowed_events": ["push"], **overrides})
    return dataclasses.replace(RepositoryActionsPolicy.from_model_data(data), id=policy_id)


def org_policy_request(**overrides: Any) -> dict[str, Any]:
    return {
        "name": "pinned",
        "enforcement": "active",
        "conditions": {
            "workflow_path": {"include": ["~ALL"], "exclude": []},
            "repository_name": {"include": ["~ALL"], "exclude": [], "protected": False},
        },
        "rules": [EVENTS_RULE],
        **overrides,
    }


def repo_policy_request(**overrides: Any) -> dict[str, Any]:
    return {
        "name": "pinned",
        "enforcement": "active",
        "conditions": {"workflow_path": {"include": ["~ALL"], "exclude": []}},
        "rules": [EVENTS_RULE],
        **overrides,
    }


async def generate_patch_and_run_it(github: GitHubProviderTestKit, *, old: Any, new: Any) -> None:
    """Generate and apply a LivePatch in one call."""
    model = ModelForContext(ORG_ID, repo_name=REPO_NAME)

    patch = model.generate_live_patch(old=old, new=new)
    await patch.apply(ORG_ID, github.provider)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Retrieval of actions policies
# ---------------------------------------------------------------------------


async def test_get_org_policies(github: GitHubProviderTestKit):
    """The details of the policies of the organization are retrieved, the ones of the enterprise are skipped."""
    # API: https://docs.github.com/en/rest/actions/policies#list-organization-actions-policies
    github.http.expect(
        "GET",
        ORG_POLICIES_URL,
        request_params=LIST_PARAMS,
        response_json={
            "total_count": 2,
            "policies": [
                {"id": 1, "name": "pinned", "source_type": "Organization"},
                {"id": 2, "name": "enterprise", "source_type": "Enterprise"},
            ],
        },
    )
    # API: https://docs.github.com/en/rest/actions/policies#get-an-organization-actions-policy
    github.http.expect(
        "GET",
        f"{ORG_POLICIES_URL}/1",
        response_json={"id": 1, "name": "pinned", "source_type": "Organization", "rules": [EVENTS_RULE]},
    )

    policies = await github.provider.get_org_actions_policies(ORG_ID)

    assert policies == [{"id": 1, "name": "pinned", "source_type": "Organization", "rules": [EVENTS_RULE]}]


async def test_get_org_policies_not_available(github: GitHubProviderTestKit):
    """An organization without access to actions policies has none."""
    github.http.expect(
        "GET",
        ORG_POLICIES_URL,
        request_params=LIST_PARAMS,
        response_status=404,
        response_text="Not Found",
    )

    assert await github.provider.get_org_actions_policies(ORG_ID) == []


async def test_get_repo_policies(github: GitHubProviderTestKit):
    """Only the policies of the repository are retrieved, the ones of the organization belong to it."""
    # API: https://docs.github.com/en/rest/actions/policies#list-repository-actions-policies
    github.http.expect(
        "GET",
        REPO_POLICIES_URL,
        request_params=LIST_PARAMS,
        response_json={
            "total_count": 2,
            "policies": [
                {"id": 1, "name": "org", "source_type": "Organization"},
                {"id": 3, "name": "pinned", "source_type": "Repository"},
            ],
        },
    )
    # API: https://docs.github.com/en/rest/actions/policies#get-a-repository-actions-policy
    github.http.expect(
        "GET",
        f"{REPO_POLICIES_URL}/3",
        response_json={"id": 3, "name": "pinned", "source_type": "Repository"},
    )

    policies = await github.provider.get_repo_actions_policies(ORG_ID, REPO_NAME)

    assert policies == [{"id": 3, "name": "pinned", "source_type": "Repository"}]


async def test_actors_are_resolved_by_name(github: GitHubProviderTestKit):
    """GitHub only provides the ids of the allowed actors, users, bots and teams are resolved by name."""
    policies: list[dict[str, Any]] = [
        {
            "id": 1,
            "name": "pinned",
            "rules": [
                {
                    "type": "restrict_actions_actors",
                    "parameters": {
                        "allowed_actors": [
                            {"id": 11, "type": "User"},
                            {"id": 12, "type": "Bot"},
                            {"id": 13, "type": "Team"},
                            {"id": 14, "type": "App"},
                            {"id": 15, "type": "IntegrationInstallation"},
                        ]
                    },
                }
            ],
        }
    ]
    # API: https://docs.github.com/en/rest/users/users#get-a-user-using-their-id
    github.http.expect("GET", "/user/11", response_json={"id": 11, "login": "alice"})
    github.http.expect("GET", "/user/12", response_json={"id": 12, "login": "dependabot[bot]"})
    # API: https://docs.github.com/en/rest/teams/teams#list-teams
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/teams",
        request_params={"per_page": "100"},
        response_json=[{"id": 13, "slug": "admins"}],
    )

    await _enrich_actions_policy_actors(policies, ORG_ID, github.provider, {"14": "my-app"})
    policy = OrganizationActionsPolicy.from_provider_data(ORG_ID, policies[0])

    assert policy.allowed_actors == [
        "@alice",
        "@dependabot[bot]",
        f"@{ORG_ID}/admins",
        "my-app",
        "IntegrationInstallation:15",
    ]


# ---------------------------------------------------------------------------
# CRUD operations for OrganizationActionsPolicy
# ---------------------------------------------------------------------------


async def test_create_org_policy(github: GitHubProviderTestKit):
    # API: https://docs.github.com/en/rest/actions/policies#create-an-organization-actions-policy
    github.http.expect(
        "POST",
        ORG_POLICIES_URL,
        request_json=org_policy_request(),
        response_status=201,
        response_json={"id": 7, "name": "pinned"},
    )

    await generate_patch_and_run_it(github, old=None, new=org_policy())


async def test_create_org_policy_with_actors(github: GitHubProviderTestKit):
    # API: https://docs.github.com/en/rest/users/users#get-a-user
    github.http.expect("GET", "/users/alice", response_json={"id": 11, "type": "User", "node_id": "U_11"})
    github.http.expect("GET", "/users/dependabot[bot]", response_json={"id": 12, "type": "Bot", "node_id": "B_12"})
    # API: https://docs.github.com/en/rest/teams/teams#get-a-team-by-name
    github.http.expect("GET", f"/orgs/{ORG_ID}/teams/admins", response_json={"id": 13, "node_id": "T_13"})
    github.http.expect(
        "POST",
        ORG_POLICIES_URL,
        request_json=org_policy_request(
            rules=[
                {
                    "type": "restrict_actions_actors",
                    "parameters": {
                        "allowed_actors": [
                            {"id": 11, "type": "User"},
                            {"id": 12, "type": "Bot"},
                            {"id": 13, "type": "Team"},
                            {"id": 2, "type": "RepositoryRole"},
                        ]
                    },
                },
            ]
        ),
        response_status=201,
        response_json={"id": 7, "name": "pinned"},
    )

    await generate_patch_and_run_it(
        github,
        old=None,
        new=org_policy(
            allowed_actors=["@alice", "@dependabot[bot]", f"@{ORG_ID}/admins", "#Maintain"], allowed_events=None
        ),
    )


async def test_update_org_policy_keeps_unsupported_rules(github: GitHubProviderTestKit):
    """A rule otterdog does not support, e.g. as GitHub does not publish it in its API yet, is kept on update."""
    current = dataclasses.replace(org_policy(7, allowed_events=["pull_request"]), unsupported_rules=[LOCKFILE_RULE])

    # API: https://docs.github.com/en/rest/actions/policies#update-an-organization-actions-policy
    github.http.expect(
        "PUT",
        f"{ORG_POLICIES_URL}/7",
        request_json=org_policy_request(rules=[EVENTS_RULE, LOCKFILE_RULE]),
        response_json={"id": 7, "name": "pinned"},
    )

    await generate_patch_and_run_it(github, old=current, new=org_policy())


async def test_update_org_policy_keeps_repository_targeting_by_property(github: GitHubProviderTestKit):
    """A policy targeting repositories by custom property, which otterdog does not support, keeps its targeting."""
    repository_property = {
        "include": [{"name": "tier", "property_values": ["core"], "source": "custom"}],
        "exclude": [],
    }
    current = OrganizationActionsPolicy.from_provider_data(
        ORG_ID,
        {
            "id": 7,
            "name": "pinned",
            "enforcement": "active",
            "conditions": {
                "repository_property": repository_property,
                "workflow_path": {"include": ["~ALL"], "exclude": []},
            },
            "rules": [{"type": "restrict_action_events", "parameters": {"allowed_events": ["pull_request"]}}],
        },
    )

    github.http.expect(
        "PUT",
        f"{ORG_POLICIES_URL}/7",
        request_json=org_policy_request(
            conditions={
                "workflow_path": {"include": ["~ALL"], "exclude": []},
                "repository_property": repository_property,
            }
        ),
        response_json={"id": 7, "name": "pinned"},
    )

    await generate_patch_and_run_it(github, old=current, new=org_policy(include_repo_names=[]))


async def test_update_repo_policy_keeps_workflows_missing_from_the_configuration(github: GitHubProviderTestKit):
    """A template that only defines the included workflows does not reset the excluded ones."""
    current = repo_policy(3, exclude_workflows=[".github/workflows/ci.yml"], allowed_events=["pull_request"])
    expected = dataclasses.replace(repo_policy(), exclude_workflows=UNSET)

    github.http.expect(
        "PUT",
        f"{REPO_POLICIES_URL}/3",
        request_json=repo_policy_request(
            conditions={"workflow_path": {"include": ["~ALL"], "exclude": [".github/workflows/ci.yml"]}}
        ),
        response_json={"id": 3, "name": "pinned"},
    )

    await generate_patch_and_run_it(github, old=current, new=expected)


async def test_update_org_policy_resolves_its_id_by_name(github: GitHubProviderTestKit):
    github.http.expect(
        "GET",
        ORG_POLICIES_URL,
        request_params=LIST_PARAMS,
        response_json={"total_count": 1, "policies": [{"id": 7, "name": "pinned", "source_type": "Organization"}]},
    )
    github.http.expect("GET", f"{ORG_POLICIES_URL}/7", response_json={"id": 7, "name": "pinned"})
    github.http.expect(
        "PUT",
        f"{ORG_POLICIES_URL}/7",
        request_json=org_policy_request(enforcement="disabled"),
        response_json={"id": 7, "name": "pinned"},
    )

    await generate_patch_and_run_it(github, old=org_policy(), new=org_policy(enforcement="disabled"))


async def test_delete_org_policy(github: GitHubProviderTestKit):
    # API: https://docs.github.com/en/rest/actions/policies#delete-an-organization-actions-policy
    github.http.expect("DELETE", f"{ORG_POLICIES_URL}/7", response_status=204)

    await generate_patch_and_run_it(github, old=org_policy(7), new=None)


# ---------------------------------------------------------------------------
# CRUD operations for RepositoryActionsPolicy
# ---------------------------------------------------------------------------


async def test_create_repo_policy(github: GitHubProviderTestKit):
    # API: https://docs.github.com/en/rest/actions/policies#create-a-repository-actions-policy
    github.http.expect(
        "POST",
        REPO_POLICIES_URL,
        request_json=repo_policy_request(
            conditions={"workflow_path": {"include": [".github/workflows/release.yml"], "exclude": []}}
        ),
        response_status=201,
        response_json={"id": 3, "name": "pinned"},
    )

    await generate_patch_and_run_it(
        github, old=None, new=repo_policy(include_workflows=[".github/workflows/release.yml"])
    )


async def test_update_repo_policy_removes_a_rule(github: GitHubProviderTestKit):
    current = repo_policy(3, allowed_actors=["#Write"])

    # API: https://docs.github.com/en/rest/actions/policies#update-a-repository-actions-policy
    github.http.expect(
        "PUT",
        f"{REPO_POLICIES_URL}/3",
        request_json=repo_policy_request(),
        response_json={"id": 3, "name": "pinned"},
    )

    await generate_patch_and_run_it(github, old=current, new=repo_policy(allowed_actors=None))


async def test_delete_repo_policy(github: GitHubProviderTestKit):
    # API: https://docs.github.com/en/rest/actions/policies#delete-a-repository-actions-policy
    github.http.expect("DELETE", f"{REPO_POLICIES_URL}/3", response_status=204)

    await generate_patch_and_run_it(github, old=repo_policy(3), new=None)
