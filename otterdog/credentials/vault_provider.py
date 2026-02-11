#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import getpass
import os
from typing import TYPE_CHECKING

import hvac
import hvac.exceptions

from otterdog.credentials import CredentialProvider, Credentials
from otterdog.logging import get_logger

if TYPE_CHECKING:
    from typing import Any

_logger = get_logger(__name__)


class VaultProvider(CredentialProvider):
    """
    A class to provide convenient access to a HashiCorp Vault.
    """

    KEY_API_TOKEN = "api_token"
    KEY_USERNAME = "username"
    KEY_PASSWORD = "password"
    KEY_TWOFA_SEED = "twofa_seed"

    DEFAULT_USERNAME_PATTERN = "{0}/github.com/username"
    DEFAULT_PASSWORD_PATTERN = "{0}/github.com/password"
    DEFAULT_TWOFA_SEED_PATTERN = "{0}/github.com/2FA-seed"
    DEFAULT_API_TOKEN_PATTERN = "{0}/github.com/api-token"

    def __init__(
        self,
        vault_addr: str | None = None,
        vault_token: str | None = None,
        mount_point: str = "cbi",
        username_pattern: str | None = None,
        password_pattern: str | None = None,
        twofa_seed_pattern: str | None = None,
        api_token_pattern: str | None = None,
        verify_ssl: bool = False,
        ca_cert: str | None = None,
        client_cert: tuple[str, str] | None = None,
        batch_mode: bool = False,
    ):
        """
        Initialize the Vault provider.

        Args:
            vault_addr: Vault server address (defaults to VAULT_ADDR environment variable)
            vault_token: Vault token for authentication (defaults to VAULT_TOKEN environment variable)
            mount_point: Vault mount point for the KV secrets engine (default: "cbi")
            username_pattern: Pattern for username secret path (default: "{0}/github.com/username")
            password_pattern: Pattern for password secret path (default: "{0}/github.com/password")
            twofa_seed_pattern: Pattern for 2FA seed secret path (default: "{0}/github.com/twofa_seed")
            api_token_pattern: Pattern for API token secret path (default: "{0}/github.com/api_token")
            verify_ssl: Whether to verify SSL certificates (default: False)
            ca_cert: Path to CA certificate bundle file for SSL verification
            client_cert: Path to client certificate file, or tuple of (cert, key) paths for mutual TLS
            batch_mode: If True, prevents interactive authentication prompts (default: False)
        """
        self._mount_point = mount_point
        self._username_pattern = username_pattern or self.DEFAULT_USERNAME_PATTERN
        self._password_pattern = password_pattern or self.DEFAULT_PASSWORD_PATTERN
        self._twofa_seed_pattern = twofa_seed_pattern or self.DEFAULT_TWOFA_SEED_PATTERN
        self._api_token_pattern = api_token_pattern or self.DEFAULT_API_TOKEN_PATTERN
        self._verify_ssl = verify_ssl
        self._ca_cert = ca_cert
        self._client_cert = client_cert
        self._batch_mode = batch_mode

        # Get Vault address from parameter or environment variable
        self._vault_addr = vault_addr or os.getenv("VAULT_ADDR", "https://secretsmanager.eclipse.org")
        if not self._vault_addr:
            raise RuntimeError(
                "Vault address not provided. Set VAULT_ADDR environment variable or pass vault_addr parameter"
            )

        _logger.debug(f"connecting to Vault at {self._vault_addr}")

        # Initialize Vault client with token
        self._vault_token = self._get_or_create_token(vault_token)
        verify_param = self._ca_cert if self._ca_cert else self._verify_ssl
        self._client = hvac.Client(
            url=self._vault_addr,
            token=self._vault_token,
            verify=verify_param,
            cert=self._client_cert,
        )

        # Verify the client is authenticated
        if not self._is_authenticated():
            raise RuntimeError("Failed to authenticate with Vault. Please check your credentials and address")

        _logger.debug("successfully authenticated with Vault")

    @property
    def mount_point(self) -> str:
        return self._mount_point

    @property
    def username_pattern(self) -> str | None:
        return self._username_pattern

    @property
    def password_pattern(self) -> str | None:
        return self._password_pattern

    @property
    def twofa_seed_pattern(self) -> str | None:
        return self._twofa_seed_pattern

    @property
    def api_token_pattern(self) -> str | None:
        return self._api_token_pattern

    def _get_or_create_token(self, vault_token: str | None) -> str:
        """
        Get Vault token from various sources or create one via authentication.

        Args:
            vault_token: Token provided as parameter

        Returns:
            Valid Vault token

        Raises:
            RuntimeError: If unable to obtain a valid token
        """
        # Try to get token from parameter, environment, or file
        token = vault_token or os.getenv("VAULT_TOKEN") or self._read_token_from_file()

        # If no token found, authenticate interactively (unless in batch mode)
        if not token:
            if self._batch_mode:
                raise RuntimeError(
                    "No Vault token found and batch mode is enabled. "
                    "Please provide a token via VAULT_TOKEN environment variable, "
                    "vault_token parameter, or ~/.vault-token file"
                )
            _logger.info("No Vault token found. Please authenticate to Vault.")
            self._authenticate_interactive()
            token = self._read_token_from_file()
            if not token:
                raise RuntimeError("Failed to obtain Vault token after authentication")

        # Verify token is valid
        verify_param = self._ca_cert if self._ca_cert else self._verify_ssl
        test_client = hvac.Client(
            url=self._vault_addr,
            token=token,
            verify=verify_param,
            cert=self._client_cert,
        )
        if not test_client.is_authenticated():
            if self._batch_mode:
                raise RuntimeError(
                    "Vault token is invalid or expired and batch mode is enabled. "
                    "Please provide a valid token via VAULT_TOKEN environment variable, "
                    "vault_token parameter, or ~/.vault-token file"
                )
            _logger.warning("Vault token is invalid or expired. Please authenticate again.")
            self._authenticate_interactive()
            token = self._read_token_from_file()
            if not token:
                raise RuntimeError("Failed to obtain Vault token after re-authentication")

            # Verify new token
            test_client = hvac.Client(
                url=self._vault_addr,
                token=token,
                verify=verify_param,
                cert=self._client_cert,
            )
            if not test_client.is_authenticated():
                raise RuntimeError("Vault token still invalid after re-authentication")

        return token

    def _is_authenticated(self) -> bool:
        """
        Check if the current Vault client is authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        try:
            return self._client.is_authenticated()
        except Exception as e:
            _logger.debug(f"Authentication check failed: {e}")
            return False

    def _read_token_from_file(self) -> str | None:
        """
        Read Vault token from $HOME/.vault-token file.

        Returns:
            Token string if file exists and is readable, None otherwise
        """
        token_file = os.path.expanduser("~/.vault-token")

        try:
            if os.path.exists(token_file):
                with open(token_file) as f:
                    token = f.read().strip()
                    if token:
                        _logger.debug("successfully read Vault token from ~/.vault-token")
                        return token
        except Exception as e:
            _logger.debug(f"could not read token from {token_file}: {e}")

        return None

    def _write_token_to_file(self, token: str) -> None:
        """
        Write Vault token to $HOME/.vault-token file.

        Args:
            token: The token to write to file
        """
        token_file = os.path.expanduser("~/.vault-token")

        try:
            with open(token_file, "w") as f:
                f.write(token)
            # Set file permissions to 600 (read/write for owner only)
            os.chmod(token_file, 0o600)
            _logger.debug(f"successfully wrote Vault token to {token_file}")
        except Exception as e:
            _logger.warning(f"could not write token to {token_file}: {e}")

    def _authenticate_interactive(self) -> None:
        """
        Prompt user for Vault authentication interactively using LDAP method.
        The token will be saved to ~/.vault-token by the vault CLI.

        Raises:
            RuntimeError: If authentication fails
        """

        print("\n🔐 Vault Authentication Required")  # noqa: T201
        print(f"Vault Address: {self._vault_addr}")  # noqa: T201
        print("\nPlease provide your LDAP credentials:\n")  # noqa: T201

        username = os.getenv("VAULT_USERNAME")
        if not username:
            username = input("Username: ").strip()

        if not username:
            raise RuntimeError("Username cannot be empty")

        password = getpass.getpass("Password: ")

        if not password:
            raise RuntimeError("Password cannot be empty")

        _logger.debug(f"attempting LDAP authentication for user: {username}")

        # Authenticate using hvac library with LDAP method
        try:
            # Create a temporary client for authentication
            verify_param = self._ca_cert if self._ca_cert else self._verify_ssl
            auth_client = hvac.Client(
                url=self._vault_addr,
                verify=verify_param,
                cert=self._client_cert,
            )

            # Perform LDAP login
            response = auth_client.auth.ldap.login(
                username=username,
                password=password,
            )

            # Extract token from response
            token = response.get("auth", {}).get("client_token")

            if not token:
                raise RuntimeError("Failed to extract token from LDAP authentication response")

            # Save token to file for future use
            self._write_token_to_file(token)

            _logger.debug("successfully authenticated to Vault via LDAP, token saved to ~/.vault-token")

        except hvac.exceptions.InvalidPath as e:
            raise RuntimeError(f"LDAP authentication method not enabled on Vault server: {e}") from None
        except hvac.exceptions.Unauthorized as e:
            raise RuntimeError(f"Invalid LDAP credentials: {e}") from None
        except hvac.exceptions.VaultError as e:
            raise RuntimeError(f"Vault LDAP authentication failed: {e}") from None
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"Unexpected error during Vault authentication: {e}") from e

    def get_credentials(self, org_name: str, data: dict[str, Any], only_token: bool = False) -> Credentials:
        """
        Retrieve credentials from Vault.

        Args:
            org_name: Organization name
            data: Dictionary that may contain specific key mappings or secret_path
            only_token: If True, only retrieve the GitHub token

        Returns:
            Credentials object with the retrieved credentials
        """
        github_token = self._retrieve_key(self.KEY_API_TOKEN, org_name, data)

        if only_token is False:
            username = self._retrieve_key(self.KEY_USERNAME, org_name, data)
            password = self._retrieve_key(self.KEY_PASSWORD, org_name, data)
            totp_secret = self._retrieve_key(self.KEY_TWOFA_SEED, org_name, data)
        else:
            username = None
            password = None
            totp_secret = None

        return Credentials(username, password, totp_secret, github_token)

    def _retrieve_key(self, key: str, org_name: str, data: dict[str, Any]) -> str:
        """
        Retrieve a specific key from Vault.

        Args:
            key: The key to retrieve (e.g., KEY_API_TOKEN, KEY_USERNAME)
            org_name: Organization name
            data: Dictionary that may contain specific key overrides

        Returns:
            The value of the requested key
        """
        resolved_key = data.get(key)
        strict = True

        if resolved_key is None:
            match key:
                case VaultProvider.KEY_USERNAME:
                    pattern = self.username_pattern
                case VaultProvider.KEY_PASSWORD:
                    pattern = self.password_pattern
                case VaultProvider.KEY_TWOFA_SEED:
                    pattern = self.twofa_seed_pattern
                    strict = False
                case VaultProvider.KEY_API_TOKEN:
                    pattern = self.api_token_pattern
                    strict = False
                case _:
                    raise RuntimeError(f"unexpected key '{key}'")

            if pattern:
                resolved_key = pattern.format(org_name)

        if resolved_key is None:
            raise RuntimeError(f"required key '{key}' not found in credential data")

        return self._retrieve_resolved_key(resolved_key, strict)

    def _retrieve_resolved_key(self, key: str, strict: bool = True) -> str:
        """
        Retrieve a specific secret value from Vault using a resolved key path.

        Args:
            key: The full key path in Vault (e.g., "technology.cbi/repo3.eclipse.org/token-username")
                Format: "vault_path/field_name" where the last component after "/" is the field name
            strict: If False, returns empty string on error instead of raising exception

        Returns:
            The secret value
        """
        # Split the key into path and field name
        # The last component after "/" is the field name, everything before is the path
        parts = key.rsplit("/", 1)

        if len(parts) == 2:
            vault_path, field_name = parts
        else:
            # If no "/" found, treat the entire key as path and use "value" as field name
            vault_path = key
            field_name = "value"

        _logger.info(f"retrieving field '{field_name}' from secret at path: {vault_path}")

        try:
            secret_response = self._client.secrets.kv.v2.read_secret_version(
                path=vault_path,
                mount_point=self._mount_point,
            )
            secret_data = secret_response["data"]["data"]
            secret = secret_data.get(field_name, "")

            if not secret:
                available_fields = list(secret_data.keys())
                _logger.debug(f"field '{field_name}' not found or empty, available fields: {available_fields}")
                if strict:
                    raise RuntimeError(
                        f"'{vault_path}' (field: '{field_name}') could not be retrieved from Vault:\n"
                        f"Field not found. Available fields: {available_fields}"
                    )
        except RuntimeError:
            raise
        except Exception as e:
            if strict:
                raise RuntimeError(
                    f"'{vault_path}' (field: '{field_name}') could not be retrieved from Vault:\n{e}"
                ) from None
            else:
                _logger.warning("'%s' (field: '%s') could not be retrieved from Vault:\n%s", vault_path, field_name, e)
                secret = ""

        return secret

    def get_secret(self, key_data: str) -> str:
        """
        Retrieve a specific secret value from Vault.

        Args:
            key_data: The secret path in Vault

        Returns:
            The secret value
        """
        return self._retrieve_resolved_key(key_data)

    def __repr__(self):
        return f"VaultProvider(vault_addr='{self._vault_addr}', mount_point='{self.mount_point}')"
