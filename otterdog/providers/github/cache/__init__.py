#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    from aiohttp_client_cache import CacheBackend


class CacheStrategy(ABC):
    @abstractmethod
    def get_cache_backend(self) -> CacheBackend | None: ...

    @abstractmethod
    def is_external(self) -> bool: ...

    def replace_base_url(self, base_url: str) -> str:
        return base_url

    @abstractmethod
    def get_request_parameters(self) -> dict[str, Any]: ...
