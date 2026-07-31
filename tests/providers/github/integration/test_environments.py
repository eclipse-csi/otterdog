#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************


from otterdog.models.environment import Environment

from .conftest import GitHubProviderTestKit
from .helpers.model import ModelForContext

# Constants
ORG_ID = "test-org"
REPO_NAME = "test-repo"
ENV_NAME = "test-env"


async def generate_patch_and_run_it(
    github: GitHubProviderTestKit,
    *,
    old: Environment | None,
    new: Environment | None,
):
    """Generate and apply a LivePatch in one call."""
    # Further model objects are required for context, as the relevant ModelObjects cannot be standalone.
    # This sets up a rather minimal context:
    model = ModelForContext(ORG_ID, repo_name=REPO_NAME)

    patch = model.generate_live_patch(old=old, new=new)
    await patch.apply(ORG_ID, github.provider)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CRUD operations for Environment, focusing on the "prevent_self_review" flag
# ---------------------------------------------------------------------------


async def test_create(github: GitHubProviderTestKit):
    github.http.expect(
        "PUT",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}",
        request_json={"prevent_self_review": True},
        response_json={"name": ENV_NAME},
    )

    await generate_patch_and_run_it(
        github,
        old=None,
        new=Environment.from_model_data({"name": ENV_NAME, "prevent_self_review": True}),
    )


async def test_read(github: GitHubProviderTestKit):
    github.http.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments",
        response_json={
            "total_count": 1,
            "environments": [
                {
                    "id": 1,
                    "node_id": "node_id_1",
                    "name": ENV_NAME,
                    "protection_rules": [
                        {
                            "id": 1,
                            "node_id": "node_id_2",
                            "type": "required_reviewers",
                            "prevent_self_review": True,
                            "reviewers": [],
                        },
                    ],
                    "deployment_branch_policy": None,
                },
            ],
        },
    )

    # Following two lines are taken from GitHubOrganization.load_from_provider().
    # Organization loading is a big black box, so we cannot run it directly here.
    data = await github.provider.get_repo_environments(ORG_ID, REPO_NAME)
    environments = [Environment.from_provider_data(ORG_ID, d) for d in data]

    assert len(environments) == 1
    assert environments[0].name == ENV_NAME
    assert environments[0].prevent_self_review is True


async def test_update(github: GitHubProviderTestKit):
    github.http.expect(
        "PUT",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}",
        request_json={"prevent_self_review": True},
        response_json={"name": ENV_NAME},
    )

    await generate_patch_and_run_it(
        github,
        old=Environment.from_model_data({"name": ENV_NAME, "prevent_self_review": False}),
        new=Environment.from_model_data({"name": ENV_NAME, "prevent_self_review": True}),
    )


async def test_delete(github: GitHubProviderTestKit):
    github.http.expect(
        "DELETE",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}",
        response_status=204,
    )

    await generate_patch_and_run_it(
        github,
        old=Environment.from_model_data({"name": ENV_NAME, "prevent_self_review": True}),
        new=None,
    )
