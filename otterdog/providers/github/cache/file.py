#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

from typing import TYPE_CHECKING

from . import CacheStrategy

if TYPE_CHECKING:
    from typing import Any

    from aiohttp_client_cache import CacheBackend

_AIOHTTP_CACHE_DIR = ".cache/async_http"


def file_cache(cache_dir: str = _AIOHTTP_CACHE_DIR) -> CacheStrategy:
    return _FileCache(cache_dir)


class _FileCache(CacheStrategy):
    def __init__(self, cache_dir: str):
        self._cache_dir = cache_dir

    def get_cache_backend(self) -> CacheBackend:
        from aiohttp_client_cache.backends import FileBackend

        return FileBackend(
            cache_name=self._cache_dir,
            use_temp=False,
        )

    def is_external(self) -> bool:
        return False

    def get_request_parameters(self) -> dict[str, Any]:
        return {"refresh": True}

    def __str__(self):
        return f"file-cache('{self._cache_dir}')"
