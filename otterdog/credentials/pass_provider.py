# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import os
import subprocess

from otterdog.credentials import Credentials, CredentialProvider
from otterdog import utils


class PassVault(CredentialProvider):
    """
    A class to provide convenient access to a pass vault.
    """

    def __init__(self, password_store_dir: str):
        utils.print_debug("accessing pass vault")
        status, output = subprocess.getstatusoutput("pass ls")
        if status != 0:
            raise RuntimeError(f"could not access pass vault:\n{output}")

        if password_store_dir:
            utils.print_debug(f"setting password store dir to {password_store_dir}")
            os.environ["PASSWORD_STORE_DIR"] = password_store_dir

        if status > 0:
            raise RuntimeError("pass vault is not accessible")

    def get_credentials(self, data: dict[str, str]) -> Credentials:
        github_token = self._retrieve_key("api_token", data)
        username = self._retrieve_key("username", data)
        password = self._retrieve_key("password", data)
        totp_secret = self._retrieve_key("2fa_seed", data)

        return Credentials(username, password, github_token, totp_secret)

    def get_secret(self, key_data: str) -> str:
        return self._retrieve_resolved_key(key_data)

    @staticmethod
    def _retrieve_key(key: str, data: dict[str, str]) -> str:
        resolved_key = data.get(key)

        if resolved_key is None:
            raise RuntimeError(f"required key '{key}' not found in authorization data")

        return PassVault._retrieve_resolved_key(resolved_key)

    @staticmethod
    def _retrieve_resolved_key(key: str) -> str:
        status, secret = subprocess.getstatusoutput(f"pass {key} 2>/dev/null")
        if status != 0:
            # run the process again, capturing any error output for debugging.
            _, output = subprocess.getstatusoutput(f"pass {key}")
            raise RuntimeError(f"{key} could not be retrieved from your pass vault:\n{output}")

        return secret

    def __str__(self):
        return "PassVault()"
