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

from otterdog.logging import get_logger, print_warn

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
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

    @classmethod
    def create(cls, provider_type: str, defaults: Mapping[str, Any]) -> CredentialProvider | None:
        match provider_type:
            case "bitwarden":
                from .bitwarden_provider import BitwardenVault

                valid_keys = _check_valid_keys(provider_type, defaults, BitwardenVault.__init__)
                return BitwardenVault(**valid_keys)

            case "pass":
                from .pass_provider import PassVault

                valid_keys = _check_valid_keys(provider_type, defaults, PassVault.__init__)
                return PassVault(**valid_keys)

            case "inmemory":
                from .inmemory_provider import InMemoryVault

                _check_valid_keys(provider_type, defaults, InMemoryVault.__init__)
                return InMemoryVault()

            case "plain":
                from .plain_provider import PlainVault

                _check_valid_keys(provider_type, defaults, PlainVault.__init__)
                return PlainVault()

            case _:
                return None


def _check_valid_keys(provider_type: str, defaults: Mapping[str, Any], func: Callable) -> dict[str, Any]:
    import inspect

    result = {}
    signature = inspect.signature(func)
    for k, v in defaults.items():
        if k in signature.parameters:
            result[k] = v
        else:
            print_warn(f"found unexpected key/value pair '{k}:{v}' in defaults for provider '{provider_type}'")

    return result
