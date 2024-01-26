#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import json
import re
import subprocess
from typing import Any

from otterdog import utils
from otterdog.credentials import CredentialProvider, Credentials


class BitwardenVault(CredentialProvider):
    """
    A class to provide convenient access to a bitwarden vault.
    """

    def __init__(self, api_token_key: str):
        self._api_token_key = api_token_key

        utils.print_debug("unlocking bitwarden vault")
        self._status, output = subprocess.getstatusoutput("bw unlock --check")
        if self._status != 0:
            raise RuntimeError(f"could not access bitwarden vault:\n{output}")

        if not self.is_unlocked():
            raise RuntimeError("bitwarden vault is locked, run 'bw unlock' and follow instructions first")

    def is_unlocked(self) -> bool:
        return self._status == 0

    def get_credentials(self, org_name: str, data: dict[str, Any], only_token: bool = False) -> Credentials:
        assert self.is_unlocked()

        item_id = data.get("item_id")
        if item_id is None:
            raise RuntimeError("required key 'item_id' not found in authorization data")

        api_token_key = data.get("api_token_key")
        if api_token_key is None:
            api_token_key = self._api_token_key

        status, output = subprocess.getstatusoutput(f"bw get item {item_id}")
        if status != 0:
            raise RuntimeError(f"item with id '{item_id}' not found in your bitwarden vault: {output}")

        # load the item json string and access the field containing the GitHub token
        item = json.loads(output)

        token_field = next(filter(lambda k: k["name"] == api_token_key, item.get("fields", [])), None)
        if token_field is None:
            raise RuntimeError(f"field with key '{api_token_key}' not found in item with id '{item_id}'")

        github_token = token_field.get("value")
        if github_token is None:
            raise RuntimeError(f"field with key '{api_token_key}' is empty in item with id '{item_id}'")

        if only_token is False:
            username = item["login"]["username"]
            if username is None:
                raise RuntimeError(f"no username specified in item with id '{item_id}'")

            password = item["login"]["password"]
            if password is None:
                raise RuntimeError(f"no password specified in item with id '{item_id}'")

            totp_secret = item["login"]["totp"]
            if totp_secret is None:
                raise RuntimeError(f"totp is empty in item with id '{item_id}'")
        else:
            username = None
            password = None
            totp_secret = None

        return Credentials(username, password, totp_secret, github_token)

    def get_secret(self, data: str) -> str:
        try:
            item_id, secret_key = re.split("@", data)

            status, output = subprocess.getstatusoutput(f"bw get item {item_id}")
            if status != 0:
                raise RuntimeError(f"item with id '{item_id}' not found in your bitwarden vault: {output}")

            if status != 0:
                raise RuntimeError(f"item with id '{item_id}' not found in your bitwarden vault")

            # load the item json string and access the field containing the GitHub token
            item = json.loads(output)

            secret_field = next(filter(lambda k: k["name"] == secret_key, item.get("fields", [])), None)
            if secret_field is None:
                raise RuntimeError(f"field with key '{secret_key}' not found in item with id '{item_id}'")

            secret = secret_field.get("value")
            if secret is None:
                raise RuntimeError(f"field with key '{secret_key}' is empty in item with id '{item_id}'")

            return secret
        except ValueError:
            raise RuntimeError(f"failed to parse secret data '{data}'")

    def __repr__(self):
        return f"BitWardenVault(unlocked={self.is_unlocked()})"
