#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os
import subprocess
from typing import Any

from otterdog import utils
from otterdog.credentials import CredentialProvider, Credentials


class PassVault(CredentialProvider):
    """
    A class to provide convenient access to a pass vault.
    """

    KEY_API_TOKEN = "api_token"
    KEY_USERNAME = "username"
    KEY_PASSWORD = "password"
    KEY_2FA_SEED = "2fa_seed"

    def __init__(
        self,
        password_store_dir: str,
        username_pattern: str,
        password_pattern: str,
        twofa_seed_pattern: str,
        api_token_pattern: str,
    ):
        utils.print_debug("accessing pass vault")
        status, output = subprocess.getstatusoutput("pass ls")
        if status != 0:
            raise RuntimeError(f"could not access pass vault:\n{output}")

        if password_store_dir:
            utils.print_debug(f"setting password store dir to '{password_store_dir}'")
            os.environ["PASSWORD_STORE_DIR"] = password_store_dir

        self._username_pattern = username_pattern
        self._password_pattern = password_pattern
        self._twofa_seed_pattern = twofa_seed_pattern
        self._api_token_pattern = api_token_pattern

        if status > 0:
            raise RuntimeError("pass vault is not accessible")

    def get_credentials(self, org_name: str, data: dict[str, Any], only_token: bool = False) -> Credentials:
        github_token = self._retrieve_key(self.KEY_API_TOKEN, org_name, data)

        if only_token is False:
            username = self._retrieve_key(self.KEY_USERNAME, org_name, data)
            password = self._retrieve_key(self.KEY_PASSWORD, org_name, data)
            totp_secret = self._retrieve_key(self.KEY_2FA_SEED, org_name, data)
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
                    pattern = self._username_pattern
                case PassVault.KEY_PASSWORD:
                    pattern = self._password_pattern
                case PassVault.KEY_2FA_SEED:
                    pattern = self._twofa_seed_pattern
                case PassVault.KEY_API_TOKEN:
                    pattern = self._api_token_pattern
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
        status, secret = subprocess.getstatusoutput(f"pass {key} 2>/dev/null")
        if status != 0:
            # run the process again, capturing any error output for debugging.
            _, output = subprocess.getstatusoutput(f"pass {key}")

            if strict:
                raise RuntimeError(f"{key} could not be retrieved from your pass vault:\n{output}")
            else:
                utils.print_warn(f"{key} could not be retrieved from your pass vault:\n{output}")
                secret = ""

        return secret

    def __repr__(self):
        return "PassVault()"
