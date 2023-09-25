# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

from dataclasses import dataclass
from requests.auth import AuthBase

from . import AuthStrategy


@dataclass(frozen=True)
class TokenAuthStrategy(AuthStrategy):
    """
    An AuthStrategy using classic PATs.
    """

    token: str

    def get_auth(self) -> AuthBase:
        return _TokenAuth(self.token)


@dataclass(frozen=True)
class _TokenAuth(AuthBase):
    token: str

    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r
