#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from typing import Any


class AuthImpl:
    @abstractmethod
    def update_headers_with_authorization(self, headers: MutableMapping[str, Any]) -> None: ...


class AuthStrategy(ABC):
    @abstractmethod
    def get_auth(self) -> AuthImpl: ...


def app_auth(app_id: str, private_key: str) -> AuthStrategy:
    from .app import AppAuthStrategy

    return AppAuthStrategy(app_id, private_key)


def token_auth(github_token: str) -> AuthStrategy:
    from .token import TokenAuthStrategy

    return TokenAuthStrategy(github_token)
