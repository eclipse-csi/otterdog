#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses
from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

from otterdog.logging import get_logger

if TYPE_CHECKING:
    from typing import Any

_logger = get_logger(__name__)


@dataclasses.dataclass
class Credentials:
    """
    A simple data class to hold credential information to access GitHub.
    """

    _username: str | None
    _password: str | None
    _totp_secret: str | None
    _github_token: str | None

    _last_totp: str | None = None

    @property
    def username(self) -> str:
        if self._username is None:
            raise RuntimeError("username not available")
        else:
            return self._username

    @property
    def password(self) -> str:
        if self._password is None:
            raise RuntimeError("password not available")
        else:
            return self._password

    @property
    def totp(self) -> str:
        import time

        import mintotp  # type: ignore

        if self._totp_secret is None:
            raise RuntimeError("totp_secret not available")

        while True:
            totp = mintotp.totp(self._totp_secret)
            _logger.trace("generated totp '%s'", totp)

            if self._last_totp is None or totp != self._last_totp:
                self._last_totp = totp
                return totp
            else:
                _logger.info("waiting 3s till generating new totp ...")
                time.sleep(3)

    @property
    def github_token(self) -> str:
        if self._github_token is None:
            raise RuntimeError("github_token not available")
        else:
            return self._github_token

    def __str__(self) -> str:
        return f"Credentials(username={self.username})"


class CredentialProvider(Protocol):
    @abstractmethod
    def get_credentials(self, org_name: str, data: dict[str, Any], only_token: bool = False) -> Credentials: ...

    @abstractmethod
    def get_secret(self, data: str) -> str: ...
