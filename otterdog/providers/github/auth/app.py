#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from . import AuthImpl, AuthStrategy

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from typing import Any


@dataclass(frozen=True)
class AppAuthStrategy(AuthStrategy):
    """
    A strategy to authenticate as a GitHub App.
    """

    app_id: str
    private_key: str

    def get_auth(self) -> AuthImpl:
        return _AppAuth(self.app_id, self.private_key)


@dataclass
class _AppAuth(AuthImpl):
    app_id: str
    private_key: str

    _jwt: str | None = None
    _expire: datetime | None = None

    def _create_jwt(self) -> tuple[str, datetime, datetime]:
        """
        Create a JWT authenticating as a GitHub App. See
        https://docs.github.com/en/developers/apps/building-github-apps/authenticating-with-github-apps#authenticating-as-a-github-app
        """
        from jwt import JWT, jwk_from_pem
        from jwt.utils import get_int_from_datetime

        # Open PEM
        with open(self.private_key, "rb") as pem_file:
            signing_key = jwk_from_pem(pem_file.read())

        # use a start time slightly in the past
        start_time = datetime.now(UTC) - timedelta(seconds=10)
        # JWT expiration time (10 minutes maximum)
        expire_time = start_time + timedelta(minutes=10)

        payload = {
            "iat": get_int_from_datetime(start_time),
            "exp": get_int_from_datetime(expire_time),
            "iss": self.app_id,
        }

        return JWT().encode(payload, signing_key, alg="RS256"), start_time, expire_time

    def get_jwt(self) -> str:
        now = datetime.now(UTC)

        if self._jwt is None or self._expire is None or now > self._expire:
            self._jwt, _, self._expire = self._create_jwt()

        return self._jwt

    def __call__(self, r):
        self.update_headers_with_authorization(r.headers)
        return r

    def update_headers_with_authorization(self, headers: MutableMapping[str, Any]) -> None:
        headers["Authorization"] = f"Bearer {self.get_jwt()}"
