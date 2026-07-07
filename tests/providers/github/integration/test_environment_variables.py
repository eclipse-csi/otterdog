#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************


from otterdog.models.environment_variable import EnvironmentVariable

from .conftest import GitHubProviderTestKit
from .helpers.model import ModelForContext

# Constants
ORG_ID = "test-org"
REPO_NAME = "test-repo"
ENV_NAME = "test-env"


async def generate_patch_and_run_it(
    github: GitHubProviderTestKit,
    *,
    old: EnvironmentVariable | None,
    new: EnvironmentVariable | None,
):
    """Generate and apply a LivePatch in one call."""
    # Further model objects are required for context, as the relevant ModelObjects cannot be standalone.
    # This sets up a rather minimal context:
    model = ModelForContext(ORG_ID, repo_name=REPO_NAME, env_name=ENV_NAME)

    patch = model.generate_live_patch(old=old, new=new)
    await patch.apply(ORG_ID, github.provider)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CRUD operations for EnvironmentVariable
# ---------------------------------------------------------------------------


async def test_create(github: GitHubProviderTestKit):
    github.http.expect(
        "POST",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/variables",
        request_json={"name": "TEST_VAR", "value": "variable_value"},
        response_status=201,
    )

    await generate_patch_and_run_it(
        github,
        old=None,
        new=EnvironmentVariable(name="TEST_VAR", value="variable_value"),
    )


async def test_read(github: GitHubProviderTestKit):
    github.http.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/variables",
        response_json={
            "total_count": 2,
            "variables": [
                {
                    "name": "VAR_ONE",
                    "value": "value_one",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                },
                {
                    "name": "VAR_TWO",
                    "value": "value_two",
                    "created_at": "2024-01-02T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                },
            ],
        },
    )

    # Following two lines are taken from GitHubOrganization.load_from_provider().
    # Organization loading is a big black box, so we cannot run it directly here.
    data = await github.provider.get_environment_variables(ORG_ID, REPO_NAME, ENV_NAME)
    variables = [EnvironmentVariable.from_provider_data(ORG_ID, data) for data in data]

    assert variables == [
        EnvironmentVariable(name="VAR_ONE", value="value_one"),
        EnvironmentVariable(name="VAR_TWO", value="value_two"),
    ]


async def test_update(github: GitHubProviderTestKit):
    github.http.expect(
        "PATCH",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/variables/TEST_VAR",
        request_json={"value": "new_value"},
        response_status=204,
    )

    await generate_patch_and_run_it(
        github,
        old=EnvironmentVariable(name="TEST_VAR", value="old_value"),
        new=EnvironmentVariable(name="TEST_VAR", value="new_value"),
    )


async def test_delete(github: GitHubProviderTestKit):
    github.http.expect(
        "DELETE",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/variables/TEST_VAR",
        response_status=204,
    )

    await generate_patch_and_run_it(
        github,
        old=EnvironmentVariable(name="TEST_VAR", value="variable_value"),
        new=None,
    )
