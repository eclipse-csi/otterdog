#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************


from otterdog.models.organization_secret import OrganizationSecret

from .conftest import GitHubProviderTestKit
from .helpers.model import ModelForContext

# Constants
ORG_ID = "test-org"
REPO_NAME = "test-repo"
ENV_NAME = "test-env"

GITHUB_SERVER_PUBLIC_KEY = "/Iag6O/YqKnJ8a1TuxcW4bMsIYs2LJ5RrOPVt9M0yUU="
KEY_ID = "test_key_id"
PLAINTEXT_SECRET = "my_secret_value"
CIPHERTEXT = "FAKE_CIPHERTEXT"


async def generate_patch_and_run_it(
    github: GitHubProviderTestKit,
    *,
    old: OrganizationSecret | None,
    new: OrganizationSecret | None,
):
    """Generate and apply a LivePatch in one call."""
    # Further model objects are required for context, as the relevant ModelObjects cannot be standalone.
    # This sets up a rather minimal context:
    model = ModelForContext(ORG_ID, repo_name=REPO_NAME)

    patch = model.generate_live_patch(old=old, new=new)
    await patch.apply(ORG_ID, github.provider)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CRUD operations for OrganizationSecret

# Note: currently only actions secrets are supported, not Dependabot secrets.
# ---------------------------------------------------------------------------


async def test_create(github: GitHubProviderTestKit):
    github.fake_encryption((GITHUB_SERVER_PUBLIC_KEY, PLAINTEXT_SECRET), CIPHERTEXT)

    # First of all the public key is fetched.
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/secrets/public-key",
        response_json={"key_id": KEY_ID, "key": GITHUB_SERVER_PUBLIC_KEY},
    )

    # Next the secret is transmitted to GitHub in encrypted form.
    # API: https://docs.github.com/en/rest/actions/secrets#create-or-update-an-organization-secret
    github.http.expect(
        "PUT",
        f"/orgs/{ORG_ID}/actions/secrets/ORG_SECRET",
        request_json={
            "key_id": KEY_ID,
            "encrypted_value": CIPHERTEXT,
            "selected_repository_ids": [],
            "visibility": "private",
        },
        response_status=201,
    )

    await generate_patch_and_run_it(
        github,
        old=None,
        new=OrganizationSecret(
            name="ORG_SECRET", value=PLAINTEXT_SECRET, visibility="private", selected_repositories=[]
        ),
    )


async def test_read(github: GitHubProviderTestKit):
    # API: https://docs.github.com/en/rest/actions/secrets#get-an-organization-secret
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/secrets",
        response_json={
            "total_count": 2,
            "secrets": [
                {
                    "name": "ORG_SECRET_PRIVATE",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                    "visibility": "private",
                },
                {
                    "name": "ORG_SECRET_SELECTED",
                    "created_at": "2024-01-02T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "visibility": "selected",
                },
                {
                    "name": "ORG_SECRET_ALL",
                    "created_at": "2024-01-02T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "visibility": "all",
                },
            ],
        },
    )

    # For selected visibility, additional API call is made to get selected repositories
    # API: https://docs.github.com/en/rest/actions/secrets#list-selected-repositories-for-an-organization-secret
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/secrets/ORG_SECRET_SELECTED/repositories",
        response_json={
            "total_count": 1,
            "repositories": [{"name": "selected-repo"}],
        },
    )

    # Following two lines are taken from GitHubOrganization.load_from_provider().
    # Organization loading is a big black box, so we cannot run it directly here.
    data = await github.provider.get_org_secrets(ORG_ID)
    secrets = [OrganizationSecret.from_provider_data(ORG_ID, d) for d in data]

    # Secrets are not returned by GitHub API. Within the model they have a placeholder value.
    magic_value = "********"
    assert secrets == [
        OrganizationSecret(
            name="ORG_SECRET_PRIVATE",
            value=magic_value,
            visibility="private",
            selected_repositories=[],
        ),
        OrganizationSecret(
            name="ORG_SECRET_SELECTED",
            value=magic_value,
            visibility="selected",
            selected_repositories=["selected-repo"],
        ),
        OrganizationSecret(
            name="ORG_SECRET_ALL",
            value=magic_value,
            visibility="public",  # "all" is mapped to "public" in the model
            selected_repositories=[],
        ),
    ]


async def test_update(github: GitHubProviderTestKit):
    github.fake_encryption((GITHUB_SERVER_PUBLIC_KEY, PLAINTEXT_SECRET), CIPHERTEXT)

    # First of all the public key is fetched.
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/secrets/public-key",
        response_json={"key_id": KEY_ID, "key": GITHUB_SERVER_PUBLIC_KEY},
    )

    # Next the secret is transmitted to GitHub in encrypted form.
    github.http.expect(
        "PUT",
        f"/orgs/{ORG_ID}/actions/secrets/ORG_SECRET",
        request_json={
            "key_id": KEY_ID,
            "encrypted_value": CIPHERTEXT,
            "selected_repository_ids": [],
            "visibility": "private",
        },
        response_status=204,
    )

    await generate_patch_and_run_it(
        github,
        old=OrganizationSecret(name="ORG_SECRET", value="old_value", visibility="private", selected_repositories=[]),
        new=OrganizationSecret(
            name="ORG_SECRET", value=PLAINTEXT_SECRET, visibility="private", selected_repositories=[]
        ),
    )


async def test_delete(github: GitHubProviderTestKit):
    # API: https://docs.github.com/en/rest/actions/secrets#delete-an-organization-secret
    github.http.expect(
        "DELETE",
        f"/orgs/{ORG_ID}/actions/secrets/ORG_SECRET",
        response_status=204,
    )

    await generate_patch_and_run_it(
        github,
        old=OrganizationSecret(
            name="ORG_SECRET",
            value="secret_value",
            visibility="private",
            selected_repositories=[],
        ),
        new=None,
    )
