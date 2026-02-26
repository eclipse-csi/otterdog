#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from otterdog.credentials import CredentialProvider, Credentials
from otterdog.logging import get_logger

_logger = get_logger(__name__)


class PlainVault(CredentialProvider):
    """
    A class to access credentials in clear text.

    NOTE: DO NOT USE THIS PROVIDER unless for quickly testing our otterdog.
    """

    KEY_API_TOKEN = "api_token"
    KEY_USERNAME = "username"
    KEY_PASSWORD = "password"
    KEY_TWOFA_SEED = "twofa_seed"

    def get_credentials(
        self, _placeholders: dict[str, str], data: dict[str, str], only_token: bool = False
    ) -> Credentials:
        github_token = self._retrieve_key(self.KEY_API_TOKEN, data)

        if only_token is False:
            username = self._retrieve_key(self.KEY_USERNAME, data)
            password = self._retrieve_key(self.KEY_PASSWORD, data)
            totp_secret = self._retrieve_key(self.KEY_TWOFA_SEED, data)
        else:
            username = None
            password = None
            totp_secret = None

        return Credentials(username, password, totp_secret, github_token)

    def get_secret(self, key_data: str) -> str:
        raise RuntimeError("plain vault does not support secrets")

    @staticmethod
    def _retrieve_key(key: str, data: dict[str, str]) -> str:
        resolved_key = data.get(key)

        if resolved_key is None:
            raise RuntimeError(f"required key '{key}' not found in credential data")
        else:
            return resolved_key

    def __repr__(self):
        return "PlainVault()"
