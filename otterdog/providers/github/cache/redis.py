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
    from redis.asyncio.client import Redis


def redis_cache(uri: str, connection: Redis | None = None) -> CacheStrategy:
    return _RedisCache(uri, connection)


class _RedisCache(CacheStrategy):
    def __init__(self, redis_uri: str, connection: Redis | None):
        self._redis_uri = redis_uri
        self._connection = connection

    def get_cache_backend(self) -> CacheBackend:
        from aiohttp_client_cache.backends import RedisBackend

        return RedisBackend(address=self._redis_uri, connection=self._connection)

    def is_external(self) -> bool:
        return False

    def get_request_parameters(self) -> dict[str, Any]:
        return {"refresh": True}

    def __str__(self):
        return f"redis-cache('{self._redis_uri}')"
