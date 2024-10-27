#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import AuthImpl, AuthStrategy

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from typing import Any


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
