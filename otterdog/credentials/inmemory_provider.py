#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from typing import Optional

from otterdog.credentials import Credentials, CredentialProvider


class InmemoryVault(CredentialProvider):
    """
    A simple credential provider for storing tokens in memory.
    """

    KEY_API_TOKEN = "api_token"

    def get_credentials(
        self, eclipse_project: Optional[str], data: dict[str, str], only_token: bool = False
    ) -> Credentials:
        if only_token is not True:
            raise RuntimeError("in-memory vault only contains github tokens")

        github_token = data[self.KEY_API_TOKEN]
        return Credentials(None, None, None, github_token)

    def get_secret(self, key_data: str) -> str:
        raise RuntimeError("in-memory vault does not support secrets")

    def __repr__(self):
        return "InmemoryProvider()"