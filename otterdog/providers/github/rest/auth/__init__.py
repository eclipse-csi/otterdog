#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
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
