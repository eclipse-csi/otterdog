# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
import subprocess

from credentials import Credentials, CredentialProvider
import utils


class BitwardenVault(CredentialProvider):
    """
    A class to provide convenient access to a bitwarden vault.
    """

    def __init__(self, api_token_key: str):
        self._api_token_key = api_token_key

        utils.print_debug("unlocking bitwarden vault")
        self._status, _ = subprocess.getstatusoutput("bw unlock --check")
        utils.print_trace(f"result = {self._status}")

        if not self.is_unlocked():
            msg = "bitwarden vault is locked, run 'bw unlock' and follow instructions first"
            utils.exit_with_message(msg, 1)

    def is_unlocked(self) -> bool:
        return self._status == 0

    def get_credentials(self, organization: str, data: dict[str, str]) -> Credentials:
        assert self.is_unlocked()

        utils.print_debug(f"retrieving credentials with provider 'bitwarden' for organization '{organization}'")

        item_id = data.get("item_id")
        if item_id is None:
            msg = f"required key 'item_id' not found in authorization data for organization '{organization}'"
            utils.exit_with_message(msg, 1)

        api_token_key = data.get("api_token_key")
        if api_token_key is None:
            api_token_key = self._api_token_key

        status, item_json = subprocess.getstatusoutput("bw get item {}".format(item_id))
        utils.print_trace(f"result = ({status}, {item_json})")

        if status != 0:
            utils.exit_with_message(f"item with id '{item_id}' not found in your bitwarden vault", 1)

        # load the item json string and access the field containing the GitHub token
        item = json.loads(item_json)
        token_field = next(filter(lambda k: k["name"] == api_token_key, item["fields"]), None)
        if token_field is None:
            utils.exit_with_message(f"field with key '{api_token_key}' not found in item with id '{item_id}'", 1)

        github_token = token_field.get("value")
        if github_token is None:
            utils.exit_with_message(f"field with key '{api_token_key}' is empty in item with id '{item_id}'", 1)

        username = item["login"]["username"]
        if username is None:
            utils.exit_with_message(f"no username specified in item with id '{item_id}'", 1)

        password = item["login"]["password"]
        if password is None:
            utils.exit_with_message(f"no password specified in item with id '{item_id}'", 1)

        totp_secret = item["login"]["totp"]
        if totp_secret is None:
            utils.exit_with_message(f"totp is empty in item with id '{item_id}'", 1)

        return Credentials(username, password, github_token, totp_secret)

    def __str__(self):
        return "BitWardenVault(unlocked={})".format(self.is_unlocked())
