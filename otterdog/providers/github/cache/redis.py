#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from aiohttp_client_cache import CacheBackend
from redis.asyncio.client import Redis

from otterdog.providers.github.cache import CacheStrategy


def redis_cache(uri: str, connection: Redis | None = None) -> CacheStrategy:
    return _RedisCache(uri, connection)


class _RedisCache(CacheStrategy):
    def __init__(self, redis_uri: str, connection: Redis | None):
        self._redis_uri = redis_uri
        self._connection = connection

    def get_cache_backend(self) -> CacheBackend:
        from aiohttp_client_cache.backends import RedisBackend

        return RedisBackend(address=self._redis_uri, connection=self._connection)
