# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableMapping

from . import AuthStrategy, AuthImpl


@dataclass(frozen=True)
class TokenAuthStrategy(AuthStrategy):
    """
    An AuthStrategy using classic PATs.
    """

    token: str

    def get_auth(self) -> AuthImpl:
        return _TokenAuth(self.token)


@dataclass(frozen=True)
class _TokenAuth(AuthImpl):
    token: str

    def __call__(self, r):
        self.update_headers_with_authorization(r.headers)
        return r

    def update_headers_with_authorization(self, headers: MutableMapping[str, Any]) -> None:
        headers["Authorization"] = f"Bearer {self.token}"
