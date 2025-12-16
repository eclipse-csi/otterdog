#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os
from unittest.mock import MagicMock, patch

import pytest

from otterdog.credentials import Credentials


class TestVaultProvider:
    """Test suite for the Vault provider."""

    @patch("otterdog.credentials.vault_provider.hvac")
    def test_vault_provider_with_default_address(self, mock_hvac):
        """Test initialization uses default address."""
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_hvac.Client.return_value = mock_client

        from otterdog.credentials.vault_provider import VaultProvider

        provider = VaultProvider(vault_token="test-token")  # noqa: S106
        assert provider._vault_addr == "https://secretsmanager.eclipse.org"

    @patch.dict(os.environ, {"VAULT_ADDR": "https://vault.test.com"}, clear=True)
    def test_vault_provider_missing_token_batch_mode(self):
        """Test initialization fails when token missing in batch mode."""
        from otterdog.credentials.vault_provider import VaultProvider

        with pytest.raises(RuntimeError, match="No Vault token found and batch mode"):
            VaultProvider(batch_mode=True)

    @patch.dict(
        os.environ,
        {
            "VAULT_ADDR": "https://vault.test.com",
            "VAULT_TOKEN": "test-token",
        },
    )
    @patch("otterdog.credentials.vault_provider.hvac")
    def test_get_credentials_kv_v2(self, mock_hvac):
        """Test retrieving credentials from Vault KV v2."""
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {
                "data": {
                    "api-token": "ghp_test_token",
                    "username": "testuser",
                    "password": "testpass",
                    "2FA-seed": "TESTSECRET123",
                }
            }
        }
        mock_hvac.Client.return_value = mock_client

        from otterdog.credentials.vault_provider import VaultProvider

        provider = VaultProvider()
        credentials = provider.get_credentials("test-org", {})

        assert isinstance(credentials, Credentials)
        assert credentials.username == "testuser"
        assert credentials.password == "testpass"
        assert credentials.github_token == "ghp_test_token"
        # Should have been called for each credential type
        assert mock_client.secrets.kv.v2.read_secret_version.call_count == 4

    @patch.dict(
        os.environ,
        {
            "VAULT_ADDR": "https://vault.test.com",
            "VAULT_TOKEN": "test-token",
        },
    )
    @patch("otterdog.credentials.vault_provider.hvac")
    def test_get_credentials_with_path_splitting(self, mock_hvac):
        """Test that key splitting works correctly."""
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {
                "data": {
                    "email": "test@example.com",
                    "password": "my_password",
                    "token-password": "my_token_password",
                    "token-username": "my_username",
                    "username": "testuser",
                }
            }
        }
        mock_hvac.Client.return_value = mock_client

        from otterdog.credentials.vault_provider import VaultProvider

        provider = VaultProvider()

        # Test retrieving token-username
        secret = provider.get_secret("technology.cbi/repo3.eclipse.org/token-username")
        assert secret == "my_username"

        # Test retrieving token-password
        secret = provider.get_secret("technology.cbi/repo3.eclipse.org/token-password")
        assert secret == "my_token_password"

        # Test retrieving username
        secret = provider.get_secret("technology.cbi/repo3.eclipse.org/username")
        assert secret == "testuser"

        # Test retrieving email
        secret = provider.get_secret("technology.cbi/repo3.eclipse.org/email")
        assert secret == "test@example.com"

        # Verify all calls were made with correct path
        for call in mock_client.secrets.kv.v2.read_secret_version.call_args_list:
            assert call[1]["path"] == "technology.cbi/repo3.eclipse.org"
            assert call[1]["mount_point"] == "cbi"

    @patch.dict(
        os.environ,
        {
            "VAULT_ADDR": "https://vault.test.com",
            "VAULT_TOKEN": "test-token",
        },
    )
    @patch("otterdog.credentials.vault_provider.hvac")
    def test_get_secret_field_not_found(self, mock_hvac):
        """Test get_secret with missing field raises error."""
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {
                "data": {
                    "other_field": "other_value",
                }
            }
        }
        mock_hvac.Client.return_value = mock_client

        from otterdog.credentials.vault_provider import VaultProvider

        provider = VaultProvider()

        # get_secret is strict by default, so should raise error
        with pytest.raises(
            RuntimeError,
            match="'github/test-org' \\(field: 'missing_field'\\)",
        ):
            provider.get_secret("github/test-org/missing_field")
