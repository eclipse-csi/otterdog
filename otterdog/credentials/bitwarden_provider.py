#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import json
from typing import Any

from otterdog.credentials import CredentialPlaceHolders, CredentialProvider, Credentials
from otterdog.logging import get_logger
from otterdog.utils import run_command_sync

_logger = get_logger(__name__)


class BitwardenVault(CredentialProvider):
    """
    A class to provide convenient access to a bitwarden vault.
    """

    _KEY_API_TOKEN = "api_token_admin"

    def __init__(self, api_token_key: str = _KEY_API_TOKEN):
        self._api_token_key = api_token_key

        _logger.debug("unlocking bitwarden vault")
        self._status, output, error = run_command_sync("bw", "unlock", "--check")
        if self._status != 0:
            raise RuntimeError(f"could not access bitwarden vault:\n{error or output}")

        if not self.is_unlocked():
            raise RuntimeError("bitwarden vault is locked, run 'bw unlock' and follow instructions first")

    @property
    def api_token_key(self) -> str:
        return self._api_token_key

    def is_unlocked(self) -> bool:
        return self._status == 0

    @staticmethod
    def _get_item(item_id: str) -> dict[str, Any]:
        # an item id starting with a dash would be interpreted as an option by the bw cli
        if not item_id or item_id.startswith("-"):
            raise RuntimeError(f"invalid bitwarden item id '{item_id}'")

        status, output, error = run_command_sync("bw", "get", "item", item_id)
        if status != 0:
            raise RuntimeError(f"item with id '{item_id}' not found in your bitwarden vault: {error or output}")

        # the cli may emit additional output, only consider the json object itself
        try:
            start_index = output.index("{")
            end_index = output.rindex("}")
        except ValueError:
            raise RuntimeError(
                f"unexpected output while reading item with id '{item_id}' from your bitwarden vault"
            ) from None

        return json.loads(output[start_index : end_index + 1])

    def get_credentials(
        self, _placeholders: CredentialPlaceHolders, data: dict[str, str], only_token: bool = False
    ) -> Credentials:
        item_id = data.get("item_id")
        if item_id is None:
            raise RuntimeError("required key 'item_id' not found in authorization data")

        api_token_key = data.get("api_token_key")
        if api_token_key is None:
            api_token_key = self.api_token_key

        # load the item json string and access the field containing the GitHub token
        item = self._get_item(item_id)

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
            item_id, secret_key = data.split("@", 1)
        except ValueError:
            raise RuntimeError(f"failed to parse secret data '{data}'") from None

        item = self._get_item(item_id)

        secret_field = next(filter(lambda k: k["name"] == secret_key, item.get("fields", [])), None)
        if secret_field is None:
            raise RuntimeError(f"field with key '{secret_key}' not found in item with id '{item_id}'")

        secret = secret_field.get("value")
        if secret is None:
            raise RuntimeError(f"field with key '{secret_key}' is empty in item with id '{item_id}'")

        return secret

    def __repr__(self):
        return f"BitWardenVault(api_token_key='{self.api_token_key}')"
