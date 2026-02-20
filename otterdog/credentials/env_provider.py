#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from dotenv import load_dotenv

from otterdog.credentials import CredentialProvider, Credentials
from otterdog.logging import get_logger

if TYPE_CHECKING:
    from typing import Any

_logger = get_logger(__name__)


def _env_value(data: dict[str, str], key: str) -> str:
    resolved_key = data.get(key)

    if resolved_key is None:
        raise RuntimeError(f"required key '{key}' not found in credential data")

    env_value = os.getenv(resolved_key)
    if env_value is None:
        raise RuntimeError(f"environment variable '{resolved_key}' for key '{key}' not found")

    return env_value


class EnvVault(CredentialProvider):
    """
    A class to access credentials from environment variables.

    Will load .env files if available.
    """

    def __init__(self) -> None:
        super().__init__()

        # load .env file if available
        load_dotenv()

    def get_credentials(self, org_name: str, data: dict[str, Any], only_token: bool = False) -> Credentials:
        """
        Retrieves credentials from environment variables based on the provided data mapping.

        :param org_name: GitHub organization. Not needed, as data is already scoped to the org.
        :param data: config data the user has provided via otterdog.jsonnet, used to resolve env var names
        :param only_token: Whether to only retrieve the API token
        """
        _logger.debug("retrieving credentials from environment variables for org '%s'", org_name)

        github_token = _env_value(data, "api_token")

        if only_token is False:
            username = _env_value(data, "username")
            password = _env_value(data, "password")
            totp_secret = _env_value(data, "twofa_seed")
        else:
            username = None
            password = None
            totp_secret = None

        return Credentials(username, password, totp_secret, github_token)

    def get_secret(self, data: str) -> str:
        raise RuntimeError("env vault does not support secrets")

    def __repr__(self) -> str:
        return "EnvVault()"
