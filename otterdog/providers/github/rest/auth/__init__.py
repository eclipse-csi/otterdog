#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the MIT License
#  which is available at https://spdx.org/licenses/MIT.html
#  SPDX-License-Identifier: MIT
#  *******************************************************************************

from abc import ABC, abstractmethod
from typing import Any, MutableMapping

from requests.auth import AuthBase


class AuthImpl(AuthBase):
    @abstractmethod
    def update_headers_with_authorization(self, headers: MutableMapping[str, Any]) -> None:
        ...


class AuthStrategy(ABC):
    @abstractmethod
    def get_auth(self) -> AuthImpl:
        ...
