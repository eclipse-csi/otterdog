#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from logging import getLogger
from typing import TYPE_CHECKING
from uuid import uuid4

from quart_redis import get_redis  # type: ignore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = getLogger(__name__)

# the lease may expire under a holder that stalled, so ownership is checked before renewing or
# releasing it, otherwise a holder could drop the lease of the one that replaced it
_RENEW_IF_OWNED = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('expire', KEYS[1], ARGV[2]) end"
_RELEASE_IF_OWNED = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end"


class RedisLease:
    """
    Claim on a key in redis, held by at most one worker process of the webapp at a time.

    It expires after ttl seconds unless renewed, so that a worker disappearing while holding
    it does not keep it forever.
    """

    def __init__(self, key: str, ttl: int) -> None:
        self.key = key
        self.ttl = ttl
        self._token = uuid4().hex

    async def acquire(self) -> bool:
        return bool(await get_redis().set(self.key, self._token, nx=True, ex=self.ttl))

    async def renew(self) -> None:
        await get_redis().eval(_RENEW_IF_OWNED, 1, self.key, self._token, self.ttl)

    async def release(self) -> None:
        await get_redis().eval(_RELEASE_IF_OWNED, 1, self.key, self._token)

    @asynccontextmanager
    async def held(self) -> AsyncIterator[None]:
        """Keeps the acquired lease renewed while the block runs, and releases it afterward."""
        renewal = asyncio.create_task(self._keep_renewed())
        try:
            yield
        finally:
            renewal.cancel()
            await self.release()

    async def _keep_renewed(self) -> None:
        while True:
            await asyncio.sleep(self.ttl / 3)
            try:
                await self.renew()
            except Exception as ex:
                # the lease expires if it can not be renewed anymore, the work it protects goes on
                logger.warning("could not renew the lease '%s': %r", self.key, ex)
