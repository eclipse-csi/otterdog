#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************


from otterdog.models.organization_variable import OrganizationVariable

from .conftest import GitHubProviderTestKit
from .helpers.model import ModelForContext

# Constants
ORG_ID = "test-org"
REPO_NAME = "test-repo"
ENV_NAME = "test-env"


async def generate_patch_and_run_it(
    github: GitHubProviderTestKit,
    *,
    old: OrganizationVariable | None,
    new: OrganizationVariable | None,
):
    """Generate and apply a LivePatch in one call."""
    # Further model objects are required for context, as the relevant ModelObjects cannot be standalone.
    # This sets up a rather minimal context:
    model = ModelForContext(ORG_ID, repo_name=REPO_NAME)

    patch = model.generate_live_patch(old=old, new=new)
    await patch.apply(ORG_ID, github.provider)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CRUD operations for OrganizationVariable
# ---------------------------------------------------------------------------


async def test_create(github: GitHubProviderTestKit):
    # API: https://docs.github.com/en/rest/actions/variables#create-an-organization-variable
    github.http.expect(
        "POST",
        f"/orgs/{ORG_ID}/actions/variables",
        request_json={
            "name": "ORG_VAR",
            "value": "variable_value",
            "visibility": "private",
            "selected_repository_ids": [],
        },
        response_status=201,
    )

    await generate_patch_and_run_it(
        github,
        old=None,
        new=OrganizationVariable(
            name="ORG_VAR",
            value="variable_value",
            visibility="private",
            selected_repositories=[],
        ),
    )


async def test_read(github: GitHubProviderTestKit):
    # The get_variables method also fetches selected repositories for variables with selected visibility
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/variables",
        response_json={
            "total_count": 2,
            "variables": [
                {
                    "name": "ORG_VAR_PRIVATE",
                    "value": "private_value",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                    "visibility": "private",
                },
                {
                    "name": "ORG_VAR_ALL",
                    "value": "all_value",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                    "visibility": "all",
                },
                {
                    "name": "ORG_VAR_SELECTED",
                    "value": "selected_value",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                    "visibility": "selected",
                },
            ],
        },
    )

    # For selected visibility, additional API call is made to get selected repositories
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/variables/ORG_VAR_SELECTED/repositories",
        response_json={
            "total_count": 1,
            "repositories": [{"name": "selected-repo"}],
        },
    )

    # Following two lines are taken from GitHubOrganization.load_from_provider().
    # Organization loading is a big black box, so we cannot run it directly here.
    data = await github.provider.get_org_variables(ORG_ID)
    variables = [OrganizationVariable.from_provider_data(ORG_ID, d) for d in data]

    assert variables == [
        OrganizationVariable(
            name="ORG_VAR_PRIVATE",
            value="private_value",
            visibility="private",
            selected_repositories=[],
        ),
        OrganizationVariable(
            name="ORG_VAR_ALL",
            value="all_value",
            visibility="public",  # "all" is mapped to "public" in the model
            selected_repositories=[],
        ),
        OrganizationVariable(
            name="ORG_VAR_SELECTED",
            value="selected_value",
            visibility="selected",
            selected_repositories=["selected-repo"],
        ),
    ]


async def test_update(github: GitHubProviderTestKit):
    # API: https://docs.github.com/en/rest/actions/variables#update-an-organization-variable
    github.http.expect(
        "PATCH",
        f"/orgs/{ORG_ID}/actions/variables/ORG_VAR",
        request_json={"value": "new_value", "visibility": "private"},
        response_status=204,
    )

    await generate_patch_and_run_it(
        github,
        old=OrganizationVariable(
            name="ORG_VAR",
            value="old_value",
            visibility="private",
            selected_repositories=[],
        ),
        new=OrganizationVariable(
            name="ORG_VAR",
            value="new_value",
            visibility="private",
            selected_repositories=[],
        ),
    )


async def test_delete(github: GitHubProviderTestKit):
    github.http.expect(
        "DELETE",
        f"/orgs/{ORG_ID}/actions/variables/ORG_VAR",
        response_status=204,
    )

    await generate_patch_and_run_it(
        github,
        old=OrganizationVariable(
            name="ORG_VAR", value="variable_value", visibility="private", selected_repositories=[]
        ),
        new=None,
    )
