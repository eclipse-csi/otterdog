#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from otterdog.models.organization_codespaces_secret import OrganizationCodespacesSecret
from otterdog.models.organization_dependabot_secret import OrganizationDependabotSecret
from otterdog.models.repo_codespaces_secret import RepositoryCodespacesSecret
from otterdog.models.repo_dependabot_secret import RepositoryDependabotSecret

from .helpers.model import ModelForContext

if TYPE_CHECKING:
    from .conftest import GitHubProviderTestKit

ORG_ID = "test-org"
REPO_NAME = "test-repo"
PUBLIC_KEY = "/Iag6O/YqKnJ8a1TuxcW4bMsIYs2LJ5RrOPVt9M0yUU="
KEY_ID = "test_key_id"
PLAINTEXT_SECRET = "my_secret_value"
CIPHERTEXT = "FAKE_CIPHERTEXT"


@pytest.mark.parametrize(
    ("secret_class", "secret_kind", "path_prefix", "model_data"),
    [
        (
            OrganizationDependabotSecret,
            "organization Dependabot",
            f"/orgs/{ORG_ID}/dependabot/secrets",
            {"name": "ORG_DEPENDABOT_SECRET", "visibility": "private", "selected_repositories": []},
        ),
        (
            OrganizationCodespacesSecret,
            "organization Codespaces",
            f"/orgs/{ORG_ID}/codespaces/secrets",
            {"name": "ORG_CODESPACES_SECRET", "visibility": "private", "selected_repositories": []},
        ),
        (
            RepositoryDependabotSecret,
            "repository Dependabot",
            f"/repos/{ORG_ID}/{REPO_NAME}/dependabot/secrets",
            {"name": "REPO_DEPENDABOT_SECRET"},
        ),
        (
            RepositoryCodespacesSecret,
            "repository Codespaces",
            f"/repos/{ORG_ID}/{REPO_NAME}/codespaces/secrets",
            {"name": "REPO_CODESPACES_SECRET"},
        ),
    ],
)
async def test_create_special_secret(
    github: GitHubProviderTestKit,
    secret_class: type[Any],
    secret_kind: str,
    path_prefix: str,
    model_data: dict[str, Any],
) -> None:
    """Each special secret scope uses its own public key and encrypted endpoint."""
    del secret_kind  # retained as a useful parameter label when pytest reports failures
    github.fake_encryption((PUBLIC_KEY, PLAINTEXT_SECRET), CIPHERTEXT)
    github.http.expect("GET", f"{path_prefix}/public-key", response_json={"key_id": KEY_ID, "key": PUBLIC_KEY})
    github.http.expect(
        "PUT",
        f"{path_prefix}/{model_data['name']}",
        request_json={
            "key_id": KEY_ID,
            "encrypted_value": CIPHERTEXT,
            **({"visibility": "private", "selected_repository_ids": []} if "visibility" in model_data else {}),
        },
        response_status=201,
    )

    model = ModelForContext(ORG_ID, repo_name=REPO_NAME)
    secret = secret_class(value=PLAINTEXT_SECRET, **model_data)
    patch = model.generate_live_patch(old=None, new=secret)
    await patch.apply(ORG_ID, github.provider)


async def test_read_organization_special_secret_with_selected_repositories(
    github: GitHubProviderTestKit,
) -> None:
    """Selected repository metadata is read through the matching scope endpoint."""
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/dependabot/secrets",
        request_params={"per_page": "100"},
        response_json={
            "secrets": [{"name": "ORG_DEPENDABOT_SECRET", "visibility": "selected"}],
        },
    )
    github.http.expect(
        "GET",
        f"/orgs/{ORG_ID}/dependabot/secrets/ORG_DEPENDABOT_SECRET/repositories",
        request_params={"per_page": "100"},
        response_json={"repositories": [{"name": REPO_NAME}]},
    )

    secrets = await github.provider.get_org_dependabot_secrets(ORG_ID)

    assert secrets == [
        {
            "name": "ORG_DEPENDABOT_SECRET",
            "visibility": "selected",
            "selected_repositories": [{"name": REPO_NAME}],
        }
    ]


async def test_read_repository_special_secrets_follows_pagination(
    github: GitHubProviderTestKit,
) -> None:
    """Repository secret reads combine every page advertised by GitHub's Link header."""
    path = f"/repos/{ORG_ID}/{REPO_NAME}/dependabot/secrets"
    github.http.expect(
        "GET",
        path,
        request_params={"per_page": "100"},
        response_json={"secrets": [{"name": "FIRST_SECRET"}]},
        response_links={"next": {"url": (f"https://api.github.com{path}?page=2&per_page=100")}},
    )
    github.http.expect(
        "GET",
        path,
        request_params={"page": "2", "per_page": "100"},
        response_json={"secrets": [{"name": "SECOND_SECRET"}]},
    )

    secrets = await github.provider.get_repo_dependabot_secrets(ORG_ID, REPO_NAME)

    assert [secret["name"] for secret in secrets] == ["FIRST_SECRET", "SECOND_SECRET"]


@pytest.mark.parametrize("status", [403, 404])
async def test_read_special_secrets_rejects_unreadable_scope(
    github: GitHubProviderTestKit,
    status: int,
) -> None:
    """An unreadable scope must not erase configured secrets during import."""
    path = f"/repos/{ORG_ID}/{REPO_NAME}/dependabot/secrets"
    github.http.expect(
        "GET",
        path,
        request_params={"per_page": "100"},
        response_status=status,
        response_text="feature unavailable",
    )

    with pytest.raises(RuntimeError, match="failed retrieving repository_dependabot secrets"):
        await github.provider.get_repo_dependabot_secrets(ORG_ID, REPO_NAME)


async def test_read_special_secrets_surfaces_unexpected_failure(
    github: GitHubProviderTestKit,
) -> None:
    """Unexpected secret-list failures are not silently converted to empty data."""
    path = f"/repos/{ORG_ID}/{REPO_NAME}/dependabot/secrets"
    github.http.expect(
        "GET",
        path,
        request_params={"per_page": "100"},
        response_status=500,
        response_text="server failure",
    )

    with pytest.raises(RuntimeError, match="failed retrieving repository_dependabot secrets"):
        await github.provider.get_repo_dependabot_secrets(ORG_ID, REPO_NAME)


async def test_read_organization_special_secret_rejects_unreadable_selected_repositories(
    github: GitHubProviderTestKit,
) -> None:
    """An unreadable repository selection must not be imported as an empty selection."""
    path = f"/orgs/{ORG_ID}/dependabot/secrets"
    github.http.expect(
        "GET",
        path,
        request_params={"per_page": "100"},
        response_json={"secrets": [{"name": "ORG_DEPENDABOT_SECRET", "visibility": "selected"}]},
    )
    github.http.expect(
        "GET",
        f"{path}/ORG_DEPENDABOT_SECRET/repositories",
        request_params={"per_page": "100"},
        response_status=404,
        response_text="feature unavailable",
    )

    with pytest.raises(RuntimeError, match="failed retrieving organization_dependabot secrets"):
        await github.provider.get_org_dependabot_secrets(ORG_ID)


@pytest.mark.parametrize(
    ("secret_class", "path_prefix", "name", "scope_data"),
    [
        (
            OrganizationDependabotSecret,
            f"/orgs/{ORG_ID}/dependabot/secrets",
            "ORG_DEPENDABOT_SECRET",
            {"visibility": "private", "selected_repositories": []},
        ),
        (
            OrganizationCodespacesSecret,
            f"/orgs/{ORG_ID}/codespaces/secrets",
            "ORG_CODESPACES_SECRET",
            {"visibility": "private", "selected_repositories": []},
        ),
        (
            RepositoryDependabotSecret,
            f"/repos/{ORG_ID}/{REPO_NAME}/dependabot/secrets",
            "REPO_DEPENDABOT_SECRET",
            {},
        ),
        (
            RepositoryCodespacesSecret,
            f"/repos/{ORG_ID}/{REPO_NAME}/codespaces/secrets",
            "REPO_CODESPACES_SECRET",
            {},
        ),
    ],
)
async def test_update_special_secret(
    github: GitHubProviderTestKit,
    secret_class: type[Any],
    path_prefix: str,
    name: str,
    scope_data: dict[str, Any],
) -> None:
    """Updates use the same scope-specific key endpoint as creation."""
    github.fake_encryption((PUBLIC_KEY, PLAINTEXT_SECRET), CIPHERTEXT)
    github.http.expect("GET", f"{path_prefix}/public-key", response_json={"key_id": KEY_ID, "key": PUBLIC_KEY})
    github.http.expect(
        "PUT",
        f"{path_prefix}/{name}",
        request_json={
            "key_id": KEY_ID,
            "encrypted_value": CIPHERTEXT,
            **({"visibility": "private", "selected_repository_ids": []} if scope_data else {}),
        },
        response_status=204,
    )

    model = ModelForContext(ORG_ID, repo_name=REPO_NAME)
    old = secret_class(name=name, value="********", **scope_data)
    new = secret_class(name=name, value=PLAINTEXT_SECRET, **scope_data)
    patch = model.generate_live_patch(old=old, new=new)
    await patch.apply(ORG_ID, github.provider)


@pytest.mark.parametrize(
    ("secret_class", "path_prefix", "name"),
    [
        (OrganizationDependabotSecret, f"/orgs/{ORG_ID}/dependabot/secrets", "ORG_DEPENDABOT_SECRET"),
        (OrganizationCodespacesSecret, f"/orgs/{ORG_ID}/codespaces/secrets", "ORG_CODESPACES_SECRET"),
        (RepositoryDependabotSecret, f"/repos/{ORG_ID}/{REPO_NAME}/dependabot/secrets", "REPO_DEPENDABOT_SECRET"),
        (RepositoryCodespacesSecret, f"/repos/{ORG_ID}/{REPO_NAME}/codespaces/secrets", "REPO_CODESPACES_SECRET"),
    ],
)
async def test_delete_special_secret(
    github: GitHubProviderTestKit,
    secret_class: type[Any],
    path_prefix: str,
    name: str,
) -> None:
    """Deletion never needs to retrieve or expose a secret value."""
    github.http.expect("DELETE", f"{path_prefix}/{name}", response_status=204)

    model = ModelForContext(ORG_ID, repo_name=REPO_NAME)
    old = secret_class(
        name=name,
        value="********",
        **({"visibility": "private", "selected_repositories": []} if "Organization" in secret_class.__name__ else {}),
    )
    patch = model.generate_live_patch(old=old, new=None)
    await patch.apply(ORG_ID, github.provider)
