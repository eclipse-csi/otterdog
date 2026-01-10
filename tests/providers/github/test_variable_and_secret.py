"""
Integration tests for repository, environment, and organization secrets and variables.

Tests start from two model states (`old` → `new`) and treat the full flow from diff (LivePatch)
generation to GitHub REST API calls as the system under test.

Because the relevant logic is spread across many units and files, small isolated unit tests
tend to provide limited value. These tests focus instead on validating that the system behaves
correctly when all parts interact.

The goal is stability: as long as the externally observable behavior is unchanged, these tests
should continue to pass even if internal code is refactored or redesigned. Assertions are
therefore limited to the rather stable model objects and the extremely stable GitHub HTTP API.

The tests do not validate internal steps or intermediate state. This makes failures
harder to localize, but keeps the suite robust and focused on user-visible behavior.
"""

import pytest

from otterdog.models import LivePatch, LivePatchContext, ModelObject
from otterdog.models.environment import Environment
from otterdog.models.environment_secret import EnvironmentSecret
from otterdog.models.environment_variable import EnvironmentVariable
from otterdog.models.organization_secret import OrganizationSecret
from otterdog.models.organization_settings import OrganizationSettings
from otterdog.models.organization_variable import OrganizationVariable
from otterdog.models.repo_secret import RepositorySecret
from otterdog.models.repo_variable import RepositoryVariable
from otterdog.models.repository import Repository
from otterdog.providers.github import GitHubProvider
from tests.providers.github.github_provider_mock import GitHubProviderTestKit
from tests.providers.github.live_patch_helpers import determine_model_object, generate_live_patch

# Constants
ORG_ID = "test-org"
REPO_NAME = "test-repo"
ENV_NAME = "production"

# Shared crypto constants
GITHUB_SERVER_PUBLIC_KEY = "/Iag6O/YqKnJ8a1TuxcW4bMsIYs2LJ5RrOPVt9M0yUU="
KEY_ID = "test_key_id"
PLAINTEXT_SECRET = "my_secret_value"
CIPHERTEXT = "FAKE_CIPHERTEXT"


def build_test_context(org_id: str, repo_name: str, env_name: str):
    """Create LivePatchContext, Repository, and Environment for tests.

    Mirrors the minimal setup used in provider tests.
    """
    org_settings = OrganizationSettings.from_model_data(
        {
            "name": org_id,
            "plan": "free",
            "two_factor_requirement": True,
        }
    )

    context = LivePatchContext(
        org_id=org_id,
        repo_filter="",
        update_webhooks=False,
        update_secrets=True,
        update_filter="*",
        current_org_settings=org_settings,
        expected_org_settings=org_settings,
    )

    repository = Repository.from_model_data(
        {
            "id": 123456,
            "node_id": "R_12345",
            "name": repo_name,
            "description": "Test repository",
            "private": False,
            "has_discussions": False,
            "has_issues": True,
            "has_projects": True,
            "has_wiki": True,
            "is_template": False,
            "topics": [],
            "default_branch": "main",
            "allow_rebase_merge": True,
            "allow_merge_commit": True,
            "allow_squash_merge": True,
            "allow_auto_merge": False,
            "delete_branch_on_merge": False,
            "allow_update_branch": False,
            "squash_merge_commit_title": "COMMIT_OR_PR_TITLE",
            "squash_merge_commit_message": "COMMIT_MESSAGES",
            "merge_commit_title": "MERGE_MESSAGE",
            "merge_commit_message": "PR_TITLE",
            "archived": False,
            "allow_forking": True,
            "web_commit_signoff_required": False,
        }
    )

    environment = Environment.from_model_data(
        {
            "name": env_name,
            "wait_timer": 0,
            "prevent_self_review": False,
            "reviewers": [],
            "deployment_branch_policy": None,
        }
    )
    environment.parent_repository = repository

    return context, repository, environment


async def generate_patch_and_run_it(
    github_provider: GitHubProvider,
    *,
    new: ModelObject | None,
    old: ModelObject | None,
):
    """Generate and apply a LivePatch in one call."""

    def _generate_patch(new: ModelObject | None, old: ModelObject | None):
        """
        Creates the local default test_context, and uses that to generate a LivePatch for the given model objects.
        The trick is reconstructing the parent object from the test context, since LivePatch generation needs it.
        (The model objects themselves do not store their parents directly.)
        """

        # Objects do not store their parents directly, so we need to reconstruct them here.
        def parent_from_test_context() -> ModelObject | None:
            model_cls = determine_model_object(old, new)
            if model_cls in {RepositorySecret, RepositoryVariable}:
                return repository
            if model_cls in {EnvironmentSecret, EnvironmentVariable}:
                return environment
            if model_cls in {OrganizationSecret, OrganizationVariable}:
                return None  # Organization-level, no parent object
            raise ValueError(f"Unknown model class for parent: {model_cls}")

        context, repository, environment = build_test_context(ORG_ID, REPO_NAME, ENV_NAME)

        return generate_live_patch(
            old=old,
            new=new,
            parent_object=parent_from_test_context(),
            context=context,
        )

    async def _apply_patch(github_provider: GitHubProvider, patch: LivePatch):
        """Generate and apply a LivePatch in one call."""
        return await patch.apply(ORG_ID, github_provider)

    patch = _generate_patch(new, old)
    await _apply_patch(github_provider, patch)


# ---------------------------------------------------------------------------
# Repository secrets
# ---------------------------------------------------------------------------


# Test: add or update repository secret (parametrized)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "old",
    [
        pytest.param(None, id="create"),
        pytest.param(RepositorySecret(name="TEST_SECRET", value="old_value"), id="update"),
    ],
)
async def test_add_or_update_repository_secret(github: GitHubProviderTestKit, old: RepositorySecret | None):
    github.fake_encryption((GITHUB_SERVER_PUBLIC_KEY, PLAINTEXT_SECRET), CIPHERTEXT)

    github.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/actions/secrets/public-key",
        response_json={"key_id": KEY_ID, "key": GITHUB_SERVER_PUBLIC_KEY},
    )

    github.expect(
        "PUT",
        f"/repos/{ORG_ID}/{REPO_NAME}/actions/secrets/TEST_SECRET",
        request_json={"key_id": KEY_ID, "encrypted_value": CIPHERTEXT},
        response_status=204 if old else 201,
    )

    await generate_patch_and_run_it(
        github.provider,
        old=old,
        new=RepositorySecret(name="TEST_SECRET", value=PLAINTEXT_SECRET),
    )


@pytest.mark.asyncio
async def test_delete_repository_secret(github: GitHubProviderTestKit):
    github.expect(
        "DELETE",
        f"/repos/{ORG_ID}/{REPO_NAME}/actions/secrets/TEST_SECRET",
        response_status=204,
    )

    await generate_patch_and_run_it(
        github.provider,
        old=RepositorySecret(name="TEST_SECRET", value="secret_value"),
        new=None,
    )


# ---------------------------------------------------------------------------
# Repository variables
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_repository_variable(github: GitHubProviderTestKit):
    github.expect(
        "POST",
        f"/repos/{ORG_ID}/{REPO_NAME}/actions/variables",
        request_json={"name": "TEST_VAR", "value": "variable_value"},
        response_status=201,
    )

    await generate_patch_and_run_it(
        github.provider,
        old=None,
        new=RepositoryVariable(name="TEST_VAR", value="variable_value"),
    )


@pytest.mark.asyncio
async def test_update_repository_variable(github: GitHubProviderTestKit):
    github.expect(
        "PATCH",
        f"/repos/{ORG_ID}/{REPO_NAME}/actions/variables/TEST_VAR",
        request_json={"value": "new_value"},
        response_status=204,
    )

    await generate_patch_and_run_it(
        github.provider,
        old=RepositoryVariable(name="TEST_VAR", value="old_value"),
        new=RepositoryVariable(name="TEST_VAR", value="new_value"),
    )


@pytest.mark.asyncio
async def test_delete_repository_variable(github: GitHubProviderTestKit):
    github.expect(
        "DELETE",
        f"/repos/{ORG_ID}/{REPO_NAME}/actions/variables/TEST_VAR",
        response_status=204,
    )

    await generate_patch_and_run_it(
        github.provider,
        old=RepositoryVariable(name="TEST_VAR", value="variable_value"),
        new=None,
    )


# ---------------------------------------------------------------------------
# Environment secrets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "old",
    [
        pytest.param(None, id="create"),
        pytest.param(EnvironmentSecret(name="ENV_SECRET", value="old_value"), id="update"),
    ],
)
async def test_add_or_update_environment_secret(github: GitHubProviderTestKit, old: EnvironmentSecret | None):
    github.fake_encryption((GITHUB_SERVER_PUBLIC_KEY, PLAINTEXT_SECRET), CIPHERTEXT)

    github.expect(
        "GET",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/secrets/public-key",
        response_json={"key_id": KEY_ID, "key": GITHUB_SERVER_PUBLIC_KEY},
    )

    github.expect(
        "PUT",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/secrets/ENV_SECRET",
        request_json={"key_id": KEY_ID, "encrypted_value": CIPHERTEXT},
        response_status=204 if old else 201,
    )

    await generate_patch_and_run_it(
        github.provider,
        old=old,
        new=EnvironmentSecret(name="ENV_SECRET", value=PLAINTEXT_SECRET),
    )


@pytest.mark.asyncio
async def test_delete_environment_secret(github: GitHubProviderTestKit):
    github.expect(
        "DELETE",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/secrets/ENV_SECRET",
        response_status=204,
    )

    await generate_patch_and_run_it(
        github.provider,
        old=EnvironmentSecret(name="ENV_SECRET", value="secret_value"),
        new=None,
    )


# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_environment_variable(github: GitHubProviderTestKit):
    github.expect(
        "POST",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/variables",
        request_json={"name": "ENV_VAR", "value": "env_var_value"},
        response_status=201,
    )

    await generate_patch_and_run_it(
        github.provider,
        new=EnvironmentVariable(name="ENV_VAR", value="env_var_value"),
        old=None,
    )


@pytest.mark.asyncio
async def test_update_environment_variable(github: GitHubProviderTestKit):
    github.expect(
        "PATCH",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/variables/ENV_VAR",
        request_json={"value": "new_value"},
        response_status=204,
    )

    await generate_patch_and_run_it(
        github.provider,
        old=EnvironmentVariable(name="ENV_VAR", value="old_value"),
        new=EnvironmentVariable(name="ENV_VAR", value="new_value"),
    )


@pytest.mark.asyncio
async def test_delete_environment_variable(github: GitHubProviderTestKit):
    github.expect(
        "DELETE",
        f"/repos/{ORG_ID}/{REPO_NAME}/environments/{ENV_NAME}/variables/ENV_VAR",
        response_status=204,
    )

    await generate_patch_and_run_it(
        github.provider,
        old=EnvironmentVariable(name="ENV_VAR", value="variable_value"),
        new=None,
    )


# ---------------------------------------------------------------------------
# Organization secrets / variables
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "old",
    [
        pytest.param(None, id="create"),
        pytest.param(
            OrganizationSecret(name="ORG_SECRET", value="old_value", visibility="private", selected_repositories=[]),
            id="update",
        ),
    ],
)
async def test_add_or_update_organization_secret(github: GitHubProviderTestKit, old: OrganizationSecret | None):
    github.fake_encryption((GITHUB_SERVER_PUBLIC_KEY, PLAINTEXT_SECRET), CIPHERTEXT)

    github.expect(
        "GET",
        f"/orgs/{ORG_ID}/actions/secrets/public-key",
        response_json={"key_id": KEY_ID, "key": GITHUB_SERVER_PUBLIC_KEY},
    )

    github.expect(
        "PUT",
        f"/orgs/{ORG_ID}/actions/secrets/ORG_SECRET",
        request_json={
            "key_id": KEY_ID,
            "encrypted_value": CIPHERTEXT,
            "selected_repository_ids": [],
            "visibility": "private",
        },
        response_status=204 if old else 201,
    )

    await generate_patch_and_run_it(
        github.provider,
        old=old,
        new=OrganizationSecret(
            name="ORG_SECRET", value=PLAINTEXT_SECRET, visibility="private", selected_repositories=[]
        ),
    )


@pytest.mark.asyncio
async def test_delete_organization_variable(github: GitHubProviderTestKit):
    github.expect(
        "DELETE",
        f"/orgs/{ORG_ID}/actions/variables/ORG_VAR",
        response_status=204,
    )

    await generate_patch_and_run_it(
        github.provider,
        old=OrganizationVariable(
            name="ORG_VAR", value="variable_value", visibility="private", selected_repositories=[]
        ),
        new=None,
    )
