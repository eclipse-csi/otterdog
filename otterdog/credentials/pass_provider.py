#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import os
import subprocess
from typing import Optional

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

    def get_credentials(
        self, eclipse_project: Optional[str], data: dict[str, str], only_token: bool = False
    ) -> Credentials:
        github_token = self._retrieve_key(self.KEY_API_TOKEN, eclipse_project, data)

        if only_token is False:
            username = self._retrieve_key(self.KEY_USERNAME, eclipse_project, data)
            password = self._retrieve_key(self.KEY_PASSWORD, eclipse_project, data)
            totp_secret = self._retrieve_key(self.KEY_2FA_SEED, eclipse_project, data)
        else:
            username = None
            password = None
            totp_secret = None

        return Credentials(username, password, totp_secret, github_token)

    def get_secret(self, key_data: str) -> str:
        return self._retrieve_resolved_key(key_data)

    @staticmethod
    def _retrieve_key(key: str, eclipse_project: Optional[str], data: dict[str, str]) -> str:
        resolved_key = data.get(key)
        strict = True

        # custom handling for eclipse projects, the keys are organized in the format
        #    bots/<eclipse-project>/github.com/<key>
        if resolved_key is None and eclipse_project is not None:
            match key:
                case PassVault.KEY_API_TOKEN:
                    query_key = "otterdog-token"
                    strict = False
                case PassVault.KEY_2FA_SEED:
                    query_key = "2FA-seed"
                case _:
                    query_key = key

            return PassVault._retrieve_resolved_key(f"bots/{eclipse_project}/github.com/{query_key}", strict)

        if resolved_key is None:
            raise RuntimeError(f"required key '{key}' not found in authorization data")

        return PassVault._retrieve_resolved_key(resolved_key)

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
