#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import os

from dotenv import load_dotenv

from otterdog.credentials import CredentialProvider, Credentials
from otterdog.logging import get_logger

_logger = get_logger(__name__)


class EnvVault(CredentialProvider):
    """
    A class to access credentials from environment variables.

    Will load .env files if available.
    """

    def __init__(
        self,
        api_token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        twofa_seed: str | None = None,
    ) -> None:
        super().__init__()

        # Note: these parameters are filled automatically by `config.py` when they exist in
        # the `defaults.env` section of the config.
        # They are used as default env var names if no org-specific settings are provided.
        self._default_keys = {
            key: value
            for key, value in {
                "api_token": api_token,
                "username": username,
                "password": password,
                "twofa_seed": twofa_seed,
            }.items()
            if value is not None
        }

        # load .env file if available.
        load_dotenv()

    def _env_value(self, placeholders: dict[str, str], data: dict[str, str], key: str) -> str:
        """
        Resolves the environment variable name for the given key based on the provided data
        and retrieves its value from the environment.

        For defaults, placeholders like `{0}` or `{org_name}` can be used based on the
        centrally-provided substitution values. For org-specific settings, the value is used as-is.
        """

        if env_variable := data.get(key):
            # Org-specific setting has priority - use as-is, no placeholder replacement
            if "{" in env_variable or "}" in env_variable:
                raise RuntimeError(
                    f"placeholders '{{' or '}}' in org-specific setting for key '{key}' are not allowed: {env_variable}"
                )

        elif env_variable := self._default_keys.get(key):
            # Use default setting + optionally replace {...} placeholders
            env_variable = env_variable.format_map(
                {
                    placeholder_key: placeholder_value.upper().replace(" ", "_").replace("-", "_")
                    for placeholder_key, placeholder_value in placeholders.items()
                }
            )
        else:
            raise RuntimeError(f"required key '{key}' not found in credential data")

        _logger.debug(
            "%s: retrieving from environment variable %s (%s)",
            key,
            env_variable,
            "org setting" if key in data else "default setting",
        )

        # Note: never log env_value. It's a secret.
        env_value = os.getenv(env_variable)
        if env_value is None:
            raise RuntimeError(f"environment variable '{env_variable}' for key '{key}' not found")

        return env_value

    def get_credentials(
        self, placeholders: dict[str, str], data: dict[str, str], only_token: bool = False
    ) -> Credentials:
        """
        Retrieves credentials from environment variables based on the provided data mapping.

        :param placeholders: precomputed substitution values used to resolve env var names
        :param data: config data the user has provided via otterdog.jsonnet, used to resolve env var names
        :param only_token: Whether to only retrieve the API token
        """
        github_token = self._env_value(placeholders, data, "api_token")

        if only_token is False:
            username = self._env_value(placeholders, data, "username")
            password = self._env_value(placeholders, data, "password")
            totp_secret = self._env_value(placeholders, data, "twofa_seed")
        else:
            username = None
            password = None
            totp_secret = None

        return Credentials(username, password, totp_secret, github_token)

    def get_secret(self, data: str) -> str:
        raise RuntimeError("env vault does not support secrets")

    def __repr__(self) -> str:
        return "EnvVault()"
