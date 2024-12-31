#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from subprocess import getstatusoutput
from typing import TYPE_CHECKING

from otterdog.credentials import CredentialProvider, Credentials
from otterdog.logging import get_logger

if TYPE_CHECKING:
    from typing import Any

_logger = get_logger(__name__)


class PassVault(CredentialProvider):
    """
    A class to provide convenient access to a pass vault.
    """

    KEY_API_TOKEN = "api_token"
    KEY_USERNAME = "username"
    KEY_PASSWORD = "password"
    KEY_TWOFA_SEED = "twofa_seed"

    def __init__(
        self,
        password_store_dir: str | None = None,
        username_pattern: str | None = None,
        password_pattern: str | None = None,
        twofa_seed_pattern: str | None = None,
        api_token_pattern: str | None = None,
    ):
        _logger.debug("accessing pass vault")
        status, output = getstatusoutput("pass ls")  # noqa: S605, S607
        if status != 0:
            raise RuntimeError(f"could not access pass vault:\n{output}")

        self._password_store_dir = password_store_dir
        if password_store_dir:
            import os

            _logger.debug("setting password store dir to '%s'", password_store_dir)
            os.environ["PASSWORD_STORE_DIR"] = password_store_dir

        self._username_pattern = username_pattern
        self._password_pattern = password_pattern
        self._twofa_seed_pattern = twofa_seed_pattern
        self._api_token_pattern = api_token_pattern

        if status > 0:
            raise RuntimeError("pass vault is not accessible")

    @property
    def password_store_dir(self) -> str | None:
        return self._password_store_dir

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

    def get_credentials(self, org_name: str, data: dict[str, Any], only_token: bool = False) -> Credentials:
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

    def get_secret(self, key_data: str) -> str:
        return self._retrieve_resolved_key(key_data)

    def _retrieve_key(self, key: str, org_name: str, data: dict[str, str]) -> str:
        resolved_key = data.get(key)
        strict = True

        if resolved_key is None:
            match key:
                case PassVault.KEY_USERNAME:
                    pattern = self.username_pattern
                case PassVault.KEY_PASSWORD:
                    pattern = self.password_pattern
                case PassVault.KEY_TWOFA_SEED:
                    pattern = self.twofa_seed_pattern
                case PassVault.KEY_API_TOKEN:
                    pattern = self.api_token_pattern
                    strict = False
                case _:
                    raise RuntimeError(f"unexpected key '{key}'")

            if pattern:
                resolved_key = pattern.format(org_name)

        if resolved_key is None:
            raise RuntimeError(f"required key '{key}' not found in credential data")

        return PassVault._retrieve_resolved_key(resolved_key, strict)

    @staticmethod
    def _retrieve_resolved_key(key: str, strict: bool = True) -> str:
        status, secret = getstatusoutput(f"pass {key} 2>/dev/null")  # noqa: S605
        if status != 0:
            # run the process again, capturing any error output for debugging.
            _, output = getstatusoutput(f"pass {key}")  # noqa: S605

            if strict:
                raise RuntimeError(f"'{key}' could not be retrieved from your pass vault:\n{output}")
            else:
                _logger.warning("'%s' could not be retrieved from your pass vault:\n%s", key, output)
                secret = ""

        return secret

    def __repr__(self):
        return f"PassVault(password_store_dir='{self.password_store_dir}')"
