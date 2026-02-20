#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""Tests for EnvVault, the environment-based credential provider.

This test module verifies that EnvVault:
- loads credential values from a .env file via python-dotenv,
- resolves usernames, passwords, TOTP seeds, and API tokens from environment variables,
- supports token-only credential retrieval when requested,
- raises clear runtime errors for missing configuration keys or environment variables,
- rejects secret retrieval operations that it does not support
"""

import pytest
from dotenv import load_dotenv as dotenv_load_dotenv

from otterdog.config import CredentialResolver, OtterdogConfig
from otterdog.credentials import Credentials
from otterdog.credentials.env_provider import EnvVault


def _credential_data() -> dict[str, str]:
    """Maps credential keys to environment-variable names as provided by otterdog.jsonnet."""
    return {
        "username": "OTTER_USERNAME",
        "password": "OTTER_PASSWORD",
        "twofa_seed": "OTTER_TOTP_SEED",
        "api_token": "OTTER_API_TOKEN",
    }


def test_init_loads_values_from_dotenv_file(tmp_path, monkeypatch):
    """
    Covers .env loading once; other tests focus on credential mapping and validation.
    No need to retest dotenv.
    """
    # The user stored the token in OTTER_TOKEN
    config = {"api_token": "OTTER_TOKEN"}
    env_file_content = "OTTER_TOKEN=42"

    # Write .env file
    env_file = tmp_path / ".env"
    _ = env_file.write_text(env_file_content)

    # Inject that .env file
    monkeypatch.setattr(
        "otterdog.credentials.env_provider.load_dotenv",
        lambda: dotenv_load_dotenv(dotenv_path=env_file),
    )

    # When we access the vault, it should load the .env file and resolve the token from OTTER_TOKEN
    c = EnvVault().get_credentials("test-org", data=config, only_token=True)

    assert c.github_token == "42"


def test_retrieve_values_from_env(monkeypatch):
    """Returns credentials object when all required values are present."""
    monkeypatch.setenv("OTTER_USERNAME", "user")
    monkeypatch.setenv("OTTER_PASSWORD", "password")
    monkeypatch.setenv("OTTER_TOTP_SEED", "seed")
    monkeypatch.setenv("OTTER_API_TOKEN", "token")

    vault = EnvVault()

    credentials = vault.get_credentials("test-org", _credential_data())

    assert isinstance(credentials, Credentials)
    assert credentials.github_token == "token"
    assert credentials.username == "user"
    assert credentials.password == "password"
    assert credentials._totp_secret == "seed"


def test_get_token_only(monkeypatch):
    """Returns token-only credentials when only_token is requested."""
    monkeypatch.setenv("OTTER_TOKEN_ONLY", "token-only")

    vault = EnvVault()

    credentials = vault.get_credentials("test-org", {"api_token": "OTTER_TOKEN_ONLY"}, only_token=True)

    assert credentials.github_token == "token-only"
    assert credentials._username is None
    assert credentials._password is None
    assert credentials._totp_secret is None


@pytest.mark.parametrize(
    "missing_key",
    [
        "api_token",
        "username",
        "password",
        "twofa_seed",
    ],
)
def test_missing_config_raises(monkeypatch, missing_key):
    """Raises a clear runtime error when required key data is missing."""
    monkeypatch.setenv("OTTER_USERNAME", "user")
    monkeypatch.setenv("OTTER_PASSWORD", "password")
    monkeypatch.setenv("OTTER_TOTP_SEED", "seed")
    monkeypatch.setenv("OTTER_API_TOKEN", "token")

    vault = EnvVault()
    data = _credential_data()
    data.pop(missing_key)

    with pytest.raises(RuntimeError) as err:
        vault.get_credentials("test-org", data)

    assert str(err.value) == f"required key '{missing_key}' not found in credential data"


def test_missing_env_var_raises(monkeypatch):
    """Raises a clear runtime error when mapped env var does not exist."""
    monkeypatch.setenv("OTTER_USERNAME", "user")
    monkeypatch.setenv("OTTER_PASSWORD", "password")
    monkeypatch.setenv("OTTER_TOTP_SEED", "seed")
    monkeypatch.delenv("OTTER_API_TOKEN", raising=False)

    vault = EnvVault()

    with pytest.raises(RuntimeError) as err:
        vault.get_credentials("test-org", _credential_data())

    assert str(err.value) == "environment variable 'OTTER_API_TOKEN' for key 'api_token' not found"


def test_get_secret_raises():
    """Rejects secret retrieval because EnvVault does not support it."""
    vault = EnvVault()

    with pytest.raises(RuntimeError) as err:
        vault.get_secret("dummy")

    assert str(err.value) == "env vault does not support secrets"


def test_repr():
    """Returns stable representation string for debugging output."""
    assert repr(EnvVault()) == "EnvVault()"


def test_get_credentials_resolves_env_provider_via_config(monkeypatch, tmp_path):
    """Ensure provider='env' is resolved through the normal config credential path."""
    monkeypatch.setenv("OTTER_API_TOKEN", "token-from-env")

    config = OtterdogConfig(
        {
            "defaults": {
                "jsonnet": {
                    "base_template": "https://github.com/otterdog/test-defaults#test-defaults.libsonnet@main",
                    "config_dir": "orgs",
                },
            },
            "organizations": [
                {
                    "name": "test-org",
                    "github_id": "test-org",
                    "credentials": {
                        "provider": "env",
                        "api_token": "OTTER_API_TOKEN",
                    },
                }
            ],
        },
        False,
        str(tmp_path),
    )

    resolver = CredentialResolver(config)
    org_config = config.get_organization_config("test-org")

    credentials = resolver.get_credentials(org_config, only_token=True)

    assert credentials.github_token == "token-from-env"
