#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from otterdog.credentials import CredentialProvider, Credentials

if TYPE_CHECKING:
    from typing import Any


class InMemoryVault(CredentialProvider):
    """
    A simple credential provider for storing tokens in memory.
    """

    KEY_API_TOKEN = "api_token"

    def get_credentials(self, org_name: str, data: dict[str, Any], only_token: bool = False) -> Credentials:
        if only_token is not True:
            raise RuntimeError("in-memory vault can only contain GitHub tokens")

        github_token = data[self.KEY_API_TOKEN]
        return Credentials(None, None, None, github_token)

    def get_secret(self, key_data: str) -> str:
        raise RuntimeError("in-memory vault does not support secrets")

    def __repr__(self):
        return "InMemoryVault()"
