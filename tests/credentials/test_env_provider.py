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


def _placeholders(org_name: str, org_id: str | None = None) -> dict[str, str]:
    return {
        "org_name": org_name,
        "org_id": org_id or org_name,
    }


class TestBasicFunctionality:
    """Tests for core EnvVault functionality: loading .env files and retrieving credentials."""

    def _credential_data(self) -> dict[str, str]:
        return {
            "username": "OTTER_USERNAME",
            "password": "OTTER_PASSWORD",
            "twofa_seed": "OTTER_TOTP_SEED",
            "api_token": "OTTER_API_TOKEN",
        }

    def test_init_loads_values_from_dotenv_file(self, tmp_path, monkeypatch):
        """Loads credentials from .env file when vault is initialized."""
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
        c = EnvVault().get_credentials(
            _placeholders("test-org"),
            data=config,
            only_token=True,
        )

        assert c.github_token == "42"

    def test_retrieve_values_from_env(self, monkeypatch):
        """Retrieves all credential fields from environment variables."""
        monkeypatch.setenv("OTTER_USERNAME", "user")
        monkeypatch.setenv("OTTER_PASSWORD", "password")
        monkeypatch.setenv("OTTER_TOTP_SEED", "seed")
        monkeypatch.setenv("OTTER_API_TOKEN", "token")

        vault = EnvVault()

        credentials = vault.get_credentials(
            _placeholders("test-org"),
            self._credential_data(),
        )

        assert isinstance(credentials, Credentials)
        assert credentials.github_token == "token"
        assert credentials.username == "user"
        assert credentials.password == "password"
        assert credentials._totp_secret == "seed"

    def test_get_token_only(self, monkeypatch):
        """Retrieves only the API token when only_token flag is set."""
        monkeypatch.setenv("OTTER_TOKEN_ONLY", "token-only")

        vault = EnvVault()

        credentials = vault.get_credentials(
            _placeholders("test-org"),
            {"api_token": "OTTER_TOKEN_ONLY"},
            only_token=True,
        )

        assert credentials.github_token == "token-only"
        assert credentials._username is None
        assert credentials._password is None
        assert credentials._totp_secret is None

    def test_repr(self):
        """Returns consistent string representation of EnvVault."""
        assert repr(EnvVault()) == "EnvVault()"


class TestErrorHandling:
    """Tests for error handling when configuration or environment variables are missing."""

    def _credential_data(self) -> dict[str, str]:
        return {
            "username": "OTTER_USERNAME",
            "password": "OTTER_PASSWORD",
            "twofa_seed": "OTTER_TOTP_SEED",
            "api_token": "OTTER_API_TOKEN",
        }

    @pytest.mark.parametrize(
        "missing_key",
        [
            "api_token",
            "username",
            "password",
            "twofa_seed",
        ],
    )
    def test_missing_config_raises(self, monkeypatch, missing_key):
        """Raises RuntimeError when required credential key is missing from config."""
        monkeypatch.setenv("OTTER_USERNAME", "user")
        monkeypatch.setenv("OTTER_PASSWORD", "password")
        monkeypatch.setenv("OTTER_TOTP_SEED", "seed")
        monkeypatch.setenv("OTTER_API_TOKEN", "token")

        vault = EnvVault()
        data = self._credential_data()
        data.pop(missing_key)

        with pytest.raises(RuntimeError) as err:
            vault.get_credentials(_placeholders("test-org"), data)

        assert str(err.value) == f"required key '{missing_key}' not found in credential data"

    def test_missing_env_var_raises(self, monkeypatch):
        """Raises RuntimeError when environment variable does not exist."""
        monkeypatch.setenv("OTTER_USERNAME", "user")
        monkeypatch.setenv("OTTER_PASSWORD", "password")
        monkeypatch.setenv("OTTER_TOTP_SEED", "seed")
        monkeypatch.delenv("OTTER_API_TOKEN", raising=False)

        vault = EnvVault()

        with pytest.raises(RuntimeError) as err:
            vault.get_credentials(_placeholders("test-org"), self._credential_data())

        assert str(err.value) == "environment variable 'OTTER_API_TOKEN' for key 'api_token' not found"

    def test_get_secret_raises(self):
        """Raises RuntimeError when secret retrieval is attempted (unsupported operation)."""
        vault = EnvVault()

        with pytest.raises(RuntimeError) as err:
            vault.get_secret("dummy")

        assert str(err.value) == "env vault does not support secrets"


class TestConfigIntegration:
    """Tests for EnvVault integration with OtterdogConfig and default handling."""

    def test_get_credentials_resolves_env_provider_via_config(self, monkeypatch, tmp_path):
        """Resolves EnvVault credentials through OtterdogConfig when provider='env'."""
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

    def test_env_defaults_are_used_when_org_credentials_missing(self, monkeypatch, tmp_path):
        """Uses default credential configuration when organization-specific config is missing."""
        monkeypatch.setenv("OTTER_DEFAULT_TOKEN", "default-token")

        config = OtterdogConfig(
            {
                "defaults": {
                    "credentials": {
                        "provider": "env",
                    },
                    "env": {
                        "api_token": "OTTER_DEFAULT_TOKEN",
                    },
                    "jsonnet": {
                        "base_template": "https://github.com/otterdog/test-defaults#test-defaults.libsonnet@main",
                        "config_dir": "orgs",
                    },
                },
                "organizations": [
                    {
                        "name": "test-org",
                        "github_id": "test-org",
                    }
                ],
            },
            False,
            str(tmp_path),
        )

        resolver = CredentialResolver(config)
        org_config = config.get_organization_config("test-org")

        credentials = resolver.get_credentials(org_config, only_token=True)

        assert credentials.github_token == "default-token"

    def test_org_specific_credentials_override_defaults(self, monkeypatch, tmp_path):
        """Organization-specific credentials take precedence over default configuration."""
        monkeypatch.setenv("ORG_SPECIFIC_TOKEN", "org-token")
        monkeypatch.setenv("DEFAULT_TOKEN", "default-token")

        config = OtterdogConfig(
            {
                "defaults": {
                    "credentials": {
                        "provider": "env",
                    },
                    "env": {
                        "api_token": "DEFAULT_TOKEN",
                    },
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
                            "api_token": "ORG_SPECIFIC_TOKEN",
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

        assert credentials.github_token == "org-token"


class TestOrgNameSubstitution:
    """Tests for {0} placeholder replacement with organization names in environment variable names.

    When {0} appears in default credential configuration, it's replaced with the organization name
    converted to uppercase with spaces and hyphens replaced by underscores.
    Example: OTTER_{0}_API_TOKEN becomes OTTER_MY_ORG_API_TOKEN for organization 'my-org'.
    """

    def test_placeholder_combined_case_transformation(self, monkeypatch):
        """Applies full transformation across all credential fields: uppercase with spaces and hyphens as underscores."""
        monkeypatch.setenv("PERFORCE_ECLIPSE_CDT_USERNAME", "alice")
        monkeypatch.setenv("PERFORCE_ECLIPSE_CDT_PASSWORD", "secret123")
        monkeypatch.setenv("PERFORCE_ECLIPSE_CDT_TOTP", "abc123def456")
        monkeypatch.setenv("PERFORCE_ECLIPSE_CDT_TOKEN", "token789")

        vault = EnvVault(
            username="PERFORCE_{org_name}_USERNAME",
            password="PERFORCE_{org_name}_PASSWORD",
            twofa_seed="PERFORCE_{org_name}_TOTP",
            api_token="PERFORCE_{org_name}_TOKEN",
        )

        credentials = vault.get_credentials(_placeholders("Eclipse CDT"), {})

        assert credentials.username == "alice"
        assert credentials.password == "secret123"
        assert credentials._totp_secret == "abc123def456"
        assert credentials.github_token == "token789"

    def test_defaults_without_placeholder_work_unchanged(self, monkeypatch):
        """Uses environment variable names directly when no {0} placeholder is present."""
        monkeypatch.setenv("STATIC_TOKEN", "token-value")

        vault = EnvVault(api_token="STATIC_TOKEN")

        credentials = vault.get_credentials(_placeholders("any-org-name"), {}, only_token=True)

        assert credentials.github_token == "token-value"

    def test_placeholder_missing_env_var_reports_transformed_name(self, monkeypatch):
        """Reports the transformed environment variable name in error messages."""
        monkeypatch.delenv("OTTER_TEST_ORG_TOKEN", raising=False)

        vault = EnvVault(api_token="OTTER_{org_name}_TOKEN")

        with pytest.raises(RuntimeError) as exc_info:
            vault.get_credentials(_placeholders("test org"), {}, only_token=True)

        # Error should reference the transformed name, not the original org name
        assert "OTTER_TEST_ORG_TOKEN" in str(exc_info.value)
