#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************


from otterdog.models.environment_secret import EnvironmentSecret

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
    old: EnvironmentSecret | None,
    new: EnvironmentSecret | None,
):
    """Generate and apply a LivePatch in one call."""
    # Further model objects are required for context, as the relevant ModelObjects cannot be standalone.
    # This sets up a rather minimal context:
    model = ModelForContext(ORG_ID, repo_name=REPO_NAME, env_name=ENV_NAME)

    patch = model.generate_live_patch(old=old, new=new)
    await patch.apply(ORG_ID, github.provider)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CRUD operations for EnvironmentSecret
# ---------------------------------------------------------------------------


async def test_create(github: GitHubProviderTestKit):
    github.fake_encryption((GITHUB_SERVER_PUBLIC_KEY, PLAINTEXT_SECRET), CIPHERTEXT)

    # First of all the public key is fetched.
    github.http.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/secrets/public-key",
        response_json={"key_id": KEY_ID, "key": GITHUB_SERVER_PUBLIC_KEY},
    )

    # Next the secret is transmitted to GitHub in encrypted form.
    github.http.expect(
        "PUT",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/secrets/TEST_SECRET",
        request_json={"key_id": KEY_ID, "encrypted_value": CIPHERTEXT},
        response_status=201,
    )

    await generate_patch_and_run_it(
        github,
        old=None,
        new=EnvironmentSecret(name="TEST_SECRET", value=PLAINTEXT_SECRET),
    )


async def test_read(github: GitHubProviderTestKit):
    github.http.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/secrets",
        response_json={
            "total_count": 2,
            "secrets": [
                {"name": "SECRET_ONE", "created_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z"},
                {"name": "SECRET_TWO", "created_at": "2024-01-02T00:00:00Z", "updated_at": "2024-01-02T00:00:00Z"},
            ],
        },
    )

    # Following two lines are taken from GitHubOrganization.load_from_provider().
    # Organization loading is a big black box, so we cannot run it directly here.
    data = await github.provider.get_environment_secrets(ORG_ID, REPO_NAME, ENV_NAME)
    secrets = [EnvironmentSecret.from_provider_data(ORG_ID, d) for d in data]

    # Secrets are not returned by GitHub API. Within the model they have a placeholder value.
    magic_value = "********"
    assert secrets == [
        EnvironmentSecret(name="SECRET_ONE", value=magic_value),
        EnvironmentSecret(name="SECRET_TWO", value=magic_value),
    ]


async def test_update(github: GitHubProviderTestKit):
    github.fake_encryption((GITHUB_SERVER_PUBLIC_KEY, PLAINTEXT_SECRET), CIPHERTEXT)

    # First of all the public key is fetched.
    github.http.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/secrets/public-key",
        response_json={"key_id": KEY_ID, "key": GITHUB_SERVER_PUBLIC_KEY},
    )

    # Next the secret is transmitted to GitHub in encrypted form.
    github.http.expect(
        "PUT",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/secrets/TEST_SECRET",
        request_json={"key_id": KEY_ID, "encrypted_value": CIPHERTEXT},
        response_status=204,
    )

    await generate_patch_and_run_it(
        github,
        old=EnvironmentSecret(name="TEST_SECRET", value="old_value"),
        new=EnvironmentSecret(name="TEST_SECRET", value=PLAINTEXT_SECRET),
    )


async def test_delete(github: GitHubProviderTestKit):
    github.http.expect(
        "DELETE",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/secrets/TEST_SECRET",
        response_status=204,
    )

    await generate_patch_and_run_it(
        github,
        old=EnvironmentSecret(name="TEST_SECRET", value="secret_value"),
        new=None,
    )
